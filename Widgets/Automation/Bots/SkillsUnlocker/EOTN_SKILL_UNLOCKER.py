from __future__ import annotations

from collections.abc import Callable, Sequence
import os
import time

import PyImGui
import PySystem

from Py4GWCoreLib import Agent, AgentArray, Dialog, GLOBAL_CACHE, ImGui, Item, Map, Player
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.enums_src.GameData_enums import Range
from Py4GWCoreLib.enums_src.GameData_enums import Range
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.native_src.internals.types import Vec2f
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.Py4GWcorelib import ConsoleLog
from Py4GWCoreLib.Routines import Routines
from Py4GWCoreLib.routines_src.Agents import Agents as RoutinesAgents
from Sources.Sky.Support import draw_support_button
from Sources.ApoSource.ApoBottingLib import wrappers as BT
from Sources.frenkeyLib.Polymock import combat, state
from Sources.frenkeyLib.Polymock.data import PolymockPieces, Polymock_Quests


BOT_NAME = "Skills Unlocker BT"
MODULE_NAME = BOT_NAME


MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
TEXTURE = os.path.join(PySystem.Console.get_projects_path(), 'Assets', 'Textures', 'Module_Icons',  "eotn_skill.png")
ICONS_PATH = os.path.join(MODULE_DIR, "icons")
MAP_TIMEOUT_MS = 190_000
MODULE_ICON = "Assets\\Textures\\Module_Icons\\eotn_skill.png"


def _build_skill_icon_index() -> dict[str, str]:
    """Index bundled skill icons by a case-insensitive stem."""
    index: dict[str, str] = {}

    try:
        filenames = os.listdir(ICONS_PATH)
    except OSError:
        return index

    for filename in filenames:
        stem, extension = os.path.splitext(filename)
        if extension.casefold() != ".png":
            continue
        index[stem.casefold()] = os.path.join(ICONS_PATH, filename)

    return index


SKILL_ICON_PATHS = _build_skill_icon_index()


def _skill_icon_path(key: str) -> str | None:
    """Return the bundled icon path for a skill key, regardless of filename case."""
    path = SKILL_ICON_PATHS.get(str(key).casefold())
    if path and os.path.isfile(path):
        return path
    return None

PathPoint = Vec2f | tuple[float, float] | tuple[int, int]
PlannerStep = tuple[str, Callable[[], BehaviorTree]]

botting_tree: BottingTree | None = None
initialized = False
_route_skill_index = 0
_route_step_index = 0
_route_previous_skill_index = -1
_show_route_controls = False


# ---------------------------------------------------------------------------
# Route coordinates - single source of truth
# ---------------------------------------------------------------------------

SEPULCHRE_LEVEL1_FRAGMENT_ROUTE_XY = (
    (-5686.91, -15401.77),
    (-5944.79, -14965.62),
    (-6191.57, -14524.03),
    (-6442.3, -14086.37),
    (-6575.49, -13594.38),
    (-6638.05, -13034.15),
    (-6629.68, -12530.43),
    (-6565.8, -12033.74),
    (-6467.0, -11541.94),
    (-6311.99, -11066.34),
    (-6137.25, -10596.09),
    (-5887.0, -10160.65),
    (-5485.02, -9848.94),
    (-5563.38, -9354.86),
    (-5582.04, -8850.15),
    (-5636.44, -8348.81),
    (-5865.55, -7897.86),
    (-6518.09, -7650.79),
    (-7015.06, -7567.73),
    (-7483.88, -7388.38),
    (-7886.51, -7079.52),
    (-8230.59, -6711.46),
    (-8512.65, -6287.49),
    (-8755.94, -5843.83),
    (-9046.1, -5434.51),
    (-9470.73, -5160.39),
    (-9865.66, -4847.15),
    (-10253.32, -4530.28),
    (-10700.16, -4265.96),
    (-11052.99, -3910.27),
    (-11355.39, -3511.4),
    (-11634.45, -3093.65),
    (-11805.14, -2622.12),
    (-11989.17, -2152.87),
    (-12191.88, -1691.31),
    (-12364.75, -1219.56),
    (-12474.15, -727.36),
    (-12580.03, -230.63),
    (-12690.33, 261.16),
    (-12800.59, 753.82),
    (-12827.22, 872.84),
)

SEPULCHRE_PROOF_OF_STRENGTH_ROUTE_XY = (
    (-7578.23, -16344.19),
    (-7092.91, -16197.64),
    (-6599.15, -16087.31),
    (-6110.94, -15971.19),
    (-5619.9, -15854.39),
    (-5366.0, -15794.0),
)

DRAKKAR_TO_REMLOK_ROUTE_XY = (
    (6949.49, 23542.63),
    (6465.62, 23406.25),
    (5986.11, 23255.91),
    (5505.69, 23099.61),
    (5014.58, 22978.79),
    (4523.75, 22876.45),
    (4038.84, 22753.05),
    (3537.72, 22728.83),
    (3044.56, 22841.23),
    (2575.94, 23020.46),
    (2108.35, 23202.46),
    (1649.56, 23404.88),
    (1192.02, 23612.16),
    (733.86, 23818.65),
    (277.39, 24026.85),
    (-215.87, 24159.21),
    (-719.95, 24188.83),
    (-1227.2, 24194.12),
    (-1730.68, 24152.36),
    (-2234.14, 24106.43),
    (-2734.59, 24052.85),
    (-3238.6, 23983.09),
    (-3735.5, 23879.83),
    (-4227.79, 23774.18),
    (-4722.49, 23656.45),
    (-5224.21, 23593.97),
    (-5724.56, 23526.72),
    (-6221.26, 23455.43),
    (-6718.96, 23383.18),
    (-7212.44, 23283.95),
    (-7705.03, 23173.42),
    (-8205.31, 23134.74),
    (-8707.81, 23134.4),
    (-9209.32, 23190.4),
    (-9632.75, 23465.46),
    (-9971.76, 23837.23),
    (-10334.22, 24189.45),
    (-10668.65, 24562.33),
    (-10808.16, 24725.78),
)

EBON_BATTLE_STANDARD_OF_HONOR_PATH_1_01 = (
    (-21593.0, 12517.0),
    (-20064.0, 11212.0),
    (-18659.0, 9768.0),
    (-17352.0, 8246.0),
    (-16126.0, 6640.0),
    (-14663.0, 5256.0),
    (-13347.0, 3732.0),
    (-11993.0, 2247.0),
    (-11088.0, 402.0),
    (-9414.0, -699.0),
    (-7532.0, 132.0),
    (-5576.0, -322.0),
    (-3621.0, -814.0),
    (-1677.0, -1304.0),
    (177.0, -2140.0),
    (1759.0, -3373.0),
    (3730.0, -3747.0),
    (5650.0, -4349.0),
    (7421.0, -5292.0),
    (8547.0, -6957.0),
    (10587.0, -6733.0),
    (12591.0, -6583.0),
    (14521.0, -7151.0),
    (16095.0, -8448.0),
    (17681.0, -9721.0),
    (19282.0, -11005.0),
    (20765.0, -12412.0),
    (22538.0, -13411.0),
    (23410.0, -13901.0),
)

EBON_BATTLE_STANDARD_OF_HONOR_PATH_2_02 = (
    (-17861.0, 16317.0),
    (-16404.0, 14900.0),
    (-16459.0, 12851.0),
    (-17542.0, 11132.0),
    (-17939.0, 9166.0),
    (-16308.0, 7932.0),
    (-15150.0, 6294.0),
    (-14010.0, 4577.0),
    (-13622.0, 2552.0),
    (-13094.0, 598.0),
    (-11367.0, -490.0),
    (-9393.0, -831.0),
    (-7616.0, -1762.0),
    (-5677.0, -2456.0),
    (-4372.0, -4015.0),
    (-3143.0, -5620.0),
    (-2954.0, -7657.0),
    (-2423.0, -9586.0),
    (-593.0, -10426.0),
    (1413.0, -10033.0),
    (3432.0, -9958.0),
    (4945.0, -8637.0),
    (6962.0, -8362.0),
    (8991.0, -8392.0),
    (4471.0, -7294.0),
    (6525.0, -7403.0),
    (8415.0, -8062.0),
    (10082.0, -9228.0),
    (11715.0, -8045.0),
)

FEEL_NO_PAIN_PATH_01 = (
    (10699.6, -7143.7),
    (10860.8, -7346.0),
    (10995.1, -7550.1),
    (10929.0, -7752.8),
    (10732.7, -7956.7),
    (10595.6, -8161.1),
    (10663.2, -8364.8),
    (10866.8, -8382.3),
    (11069.9, -8278.6),
    (11270.6, -8175.8),
    (11474.9, -8166.0),
    (11509.5, -8370.6),
    (11339.8, -8570.8),
    (11165.9, -8776.2),
    (11122.3, -8977.3),
    (11324.1, -9149.3),
    (11524.2, -9087.1),
    (11726.6, -8891.3),
    (11928.8, -8749.9),
    (12128.9, -8825.3),
    (12133.3, -9030.4),
    (11989.0, -9233.9),
    (11841.6, -9434.0),
    (11752.0, -9636.7),
    (11954.8, -9805.3),
    (12156.2, -9668.8),
    (12237.3, -9466.5),
    (12349.3, -9265.1),
    (12905.82, -9617.43),
)

WINDS_PATH_01 = (
    (14576.0, -6137.7),
    (14568.2, -5136.7),
    (14112.5, -4135.1),
    (13107.6, -3750.6),
    (12600.1, -2745.8),
    (12484.4, -1739.7),
    (12528.0, -732.3),
    (11619.6, 313.6),
    (11527.4, 1316.2),
    (10823.6, 2318.0),
)

AIR_OF_SUPERIORITY_PATH_01 = (
    (-2584.1, 515.4),
    (-3168.0, -985.5),
    (-3228.0, -2487.7),
    (-3424.8, -3989.7),
    (-4391.7, -2487.7),
    (-4291.6, -987.4),
    (-3990.1, 512.9),
    (-3273.5, 2013.5),
    (-2242.5, 3515.2),
    (-975.6, 5015.6),
    (527.6, 5854.7),
    (2031.6, 5378.3),
    (3536.6, 5030.3),
    (5041.9, 4768.3),
    (6545.9, 5184.7),
    (8050.1, 5978.9),
    (9552.6, 6651.4),
    (11053.5, 6855.5),
    (12558.9, 7385.4),
    (14059.8, 6908.5),
    (15561.8, 6764.8),
    (17064.0, 5965.7),
    (17953.4, 4465.6),
    (19457.1, 3896.6),
    (20957.5, 3474.3),
    (23571.6, 1778.8),
)

ASURAN_SCAN_PATH_01 = (
    (-11165.4, -18283.9),
    (-11328.1, -17780.3),
    (-11384.3, -17280.2),
    (-11334.4, -16778.1),
    (-11299.2, -16276.2),
    (-11329.3, -15772.8),
    (-11316.9, -15269.3),
    (-11349.1, -14767.7),
    (-11348.2, -14267.3),
    (-11384.4, -13765.5),
    (-11316.9, -13265.2),
    (-11233.8, -12765.2),
    (-11150.5, -12263.8),
    (-11067.2, -11762.9),
    (-10896.6, -11260.0),
    (-10667.6, -10758.3),
    (-10461.4, -10258.3),
    (-10254.9, -9757.7),
    (-10064.7, -9256.7),
    (-9835.3, -8756.4),
    (-9718.4, -8251.5),
    (-9640.7, -7750.0),
    (-9561.5, -7249.7),
    (-9512.5, -6749.1),
    (-9480.4, -6248.2),
    (-9458.3, -5743.9),
    (-9469.2, -5241.0),
    (-9559.7, -4740.4),
    (-9232.6, -4238.3),
    (-8888.4, -3737.5),
    (-8548.9, -3233.5),
    (-8232.0, -2729.6),
    (-8124.7, -2227.3),
    (-8145.7, -1727.3),
    (-8172.7, -1223.1),
    (-8213.0, -718.8),
    (-8263.4, -217.4),
    (-8315.9, 285.3),
    (-8388.2, 789.5),
    (-8511.6, 1292.5),
    (-8647.4, 1797.6),
    (-8766.6, 2301.6),
    (-9177.1, 2804.6),
    (-9641.8, 3305.0),
    (-9964.5, 3809.8),
    (-9928.1, 4311.3),
    (-9428.2, 4814.2),
    (-8927.0, 5191.5),
    (-8443.6, 5693.6),
    (-7941.2, 5822.0),
    (-7440.0, 5904.8),
    (-6935.2, 5990.9),
    (-6431.5, 6070.9),
    (-5925.0, 6133.0),
    (-5422.3, 6192.9),
    (-4917.6, 6210.4),
    (-4415.9, 6234.1),
    (-3914.2, 6258.1),
    (-3413.2, 6288.2),
    (-2911.0, 6320.1),
    (-2406.6, 6352.2),
    (-1902.5, 6292.1),
    (-1401.4, 6104.2),
    (-898.4, 5923.1),
    (-396.5, 5874.6),
    (107.0, 5793.2),
    (607.5, 5705.9),
    (1111.0, 5617.4),
    (1612.5, 5529.3),
    (2114.7, 5559.1),
    (2616.7, 5820.9),
    (3119.0, 6102.4),
    (3620.1, 6494.9),
    (4121.1, 6888.0),
    (4623.3, 7275.8),
    (5124.6, 7435.8),
    (5626.4, 7537.5),
    (6080.2, 7037.3),
    (6438.3, 6533.6),
    (6795.6, 6031.0),
    (7296.8, 5720.0),
    (7797.8, 5498.1),
    (8299.2, 5427.9),
    (8799.6, 5350.6),
    (9300.5, 5511.6),
    (9802.5, 5812.5),
    (10346.69, 8246.0),
    (10808.6, 6189.0),
    (11311.0, 6333.2),
    (11302.6, 5831.4),
    (11248.2, 5330.4),
    (11210.3, 4828.7),
    (11132.2, 4326.2),
    (11034.8, 3821.7),
    (10937.3, 3320.5),
    (10839.4, 2817.3),
    (10741.8, 2315.8),
    (10644.0, 1813.2),
    (10530.5, 1311.6),
    (10410.4, 807.9),
    (10264.4, 304.8),
    (10117.4, -196.6),
    (10220.3, -697.2),
    (10295.1, -1198.7),
    (9793.1, -1453.9),
    (9289.4, -1546.0),
    (8787.0, -1543.4),
    (8286.1, -1480.6),
    (7785.1, -1417.8),
    (7285.0, -1355.1),
    (6779.9, -1303.0),
    (6276.2, -1185.9),
    (5774.2, -1006.9),
    (5272.1, -1011.6),
    (4769.0, -1198.1),
    (4264.9, -1441.2),
    (3764.1, -1665.9),
    (3823.0, -2168.4),
    (4325.4, -2468.7),
    (4828.8, -2117.9),
    (5331.0, -1838.1),
    (5833.0, -1559.3),
    (6319.6, -1055.8),
    (6395.2, -554.3),
    (6346.1, -53.7),
    (6292.7, 447.5),
    (6241.4, 950.9),
    (6140.5, 1451.3),
    (6090.1, 1953.7),
    (6039.9, 2455.2),
    (5728.8, 2957.0),
    (5271.5, 3458.7),
    (4767.9, 3612.2),
    (4350.9, 3108.4),
    (3865.1, 2604.3),
    (3657.0, 2100.5),
    (3460.4, 1598.3),
    (3360.7, 1463.1),
)

# Asuran Scan / Facet of Death
ASURAN_SCAN_FACET_MODEL_ID = 6325
ASURAN_SCAN_FACET_KNOWN_SPAWN_01 = (3507.0, 1502.0)

# Keep the complete legacy search route and finish on the exact observed spawn.
ASURAN_SCAN_FACET_PATH_01 = (
    *ASURAN_SCAN_PATH_01,
    ASURAN_SCAN_FACET_KNOWN_SPAWN_01,
)

ASURAN_SCAN_FACET_SPAWN_INDICES = (
    len(ASURAN_SCAN_FACET_PATH_01) - 1,
)


RADIATION_FIELD_PATH_01 = (
    (-21603.1, 8285.9),
    (-21798.3, 9288.2),
    (-21789.4, 10290.0),
    (-21909.8, 11293.0),
    (-22083.2, 12295.0),
    (-21079.4, 12098.4),
    (-20077.3, 11811.3),
    (-19076.9, 11615.3),
    (-18075.5, 11247.0),
    (-17073.4, 10500.9),
    (-16247.2, 9500.6),
    (-15282.3, 8499.2),
    (-14280.3, 7593.8),
    (-13275.6, 7853.4),
    (-12272.0, 8145.0),
    (-11268.3, 8416.7),
    (-10266.5, 7814.2),
    (-9364.5, 6812.3),
    (-8361.9, 6094.6),
    (-7359.9, 6144.0),
    (-6355.5, 6385.9),
    (-5405.8, 7386.0),
    (-4936.1, 8388.2),
    (-4396.1, 9390.1),
    (-3394.9, 9932.9),
    (-2391.5, 9843.4),
    (-1391.0, 9588.0),
    (1618.8, 8503.5),
    (2311.4, 11804.0),
    (3313.1, 12027.4),
    (4316.5, 11849.2),
    (5316.6, 12024.3),
    (6318.5, 11885.3),
    (7320.1, 11537.4),
    (8321.1, 11136.9),
    (9321.7, 10593.2),
    (10324.7, 10049.8),
    (11326.2, 9505.4),
    (14718.8, 5965.5),
    (15255.1, 4964.5),
    (15921.5, 3964.5),
    (16391.0, 2962.0),
    (16474.3, 1958.2),
    (17130.1, 955.1),
    (17756.3, -45.2),
    (18257.8, -1046.1),
    (19065.4, -2046.7),
    (19437.0, -3050.3),
    (19807.5, -4051.0),
    (20178.1, -5052.2),
    (20671.6, -6054.6),
    (20041.9, -5054.5),
    (19039.5, -5913.2),
    (18158.3, -6913.3),
    (17246.3, -7913.5),
    (16287.2, -8914.5),
    (15287.1, -9047.3),
    (14284.6, -9227.9),
    (13283.0, -9408.5),
    (12281.7, -9672.8),
    (11281.3, -9987.0),
    (10280.3, -10117.4),
    (9278.4, -10264.2),
    (8278.3, -10399.0),
    (7275.8, -10447.3),
    (6274.1, -10469.4),
    (5271.4, -10193.3),
    (4270.0, -9822.4),
    (3268.8, -9567.0),
    (2265.5, -9244.4),
    (1263.1, -8930.2),
    (261.3, -8352.1),
    (-740.2, -7670.2),
    (-1556.0, -6669.4),
    (-2414.9, -5668.4),
    (-3224.1, -4665.7),
    (-4227.5, -3773.8),
)

TECHNOBABBLE_PATH1_01 = (
    (16333.0, 13134.0),
    (15831.3, 12689.2),
    (14826.0, 12244.9),
    (13819.6, 11800.6),
    (12815.3, 11338.3),
    (12323.8, 10334.1),
    (11980.6, 9332.0),
    (10972.8, 8700.9),
    (9966.2, 8792.9),
    (8965.1, 9574.6),
    (7958.7, 10437.8),
    (7435.5, 11444.1),
    (6956.4, 12448.6),
    (6460.2, 13452.2),
    (5804.7, 14341.9),
    (4799.9, 14136.0),
    (3795.5, 13944.2),
    (2793.6, 13807.8),
    (1791.5, 13711.2),
    (787.7, 14183.2),
    (-214.4, 13677.2),
    (-737.5, 12676.2),
    (-1511.9, 11673.6),
    (-2135.2, 10670.0),
    (-2655.5, 9665.3),
    (-3659.5, 9939.1),
    (-4665.0, 9846.3),
    (-5668.2, 9829.6),
    (-6672.9, 10007.4),
    (-7178.3, 9004.0),
    (-7180.2, 8000.7),
    (-7533.2, 9006.4),
    (-8537.4, 9423.0),
    (-9538.6, 9947.0),
    (-10539.4, 10902.5),
    (-10997.0, 11906.4),
    (-10826.9, 12910.9),
    (-10739.5, 13913.7),
    (-10731.4, 14918.5),
    (-11405.8, 16127.1),
    (-12410.1, 15642.0),
    (-13412.0, 15177.1),
    (-14418.9, 14726.5),
    (-15421.4, 14567.4),
    (-16426.4, 14590.7),
    (-17430.9, 14742.7),
    (-17579.8, 13740.1),
    (-18287.3, 14623.7),
)

TECHNOBABBLE_PATH2_02 = tuple(reversed(TECHNOBABBLE_PATH1_01))

TECHNOBABBLE_PATH3_03 = (
    (16029.7, 12397.9),
    (15026.6, 12140.9),
    (14025.6, 11883.9),
    (13371.9, 10881.3),
    (12902.8, 9874.1),
    (12694.8, 8871.6),
    (12506.1, 7866.6),
    (11497.3, 7588.6),
    (10484.8, 7371.9),
    (9480.5, 6952.3),
    (9145.1, 7044.0),
    (9620.1, 6039.9),
    (10161.9, 5033.7),
    (10405.3, 4027.2),
    (10317.9, 3024.2),
    (9724.4, 2022.1),
    (8833.3, 1015.3),
    (7832.5, 507.9),
    (6830.2, 23.6),
    (5824.7, -490.1),
    (4822.4, -1027.4),
    (3941.5, -1783.5),
    (2951.3, -2653.6),
    (2170.4, -3524.7),
    (1746.0, -4528.3),
    (1487.5, -5532.6),
    (1182.3, -6537.0),
    (1026.8, -7039.6),
)

# Technobabble / Facet of Illusions
TECHNOBABBLE_FACET_MODEL_ID = 6327
TECHNOBABBLE_FACET_KNOWN_SPAWN_01 = (6200.58, 13964.41)

# One continuous search route.  The known Facet spawn is inserted directly
# into the first leg so the player gets close enough to force the reveal.
_TECHNOBABBLE_PATH1_WITH_SPAWN = (
    *TECHNOBABBLE_PATH1_01[:14],
    TECHNOBABBLE_FACET_KNOWN_SPAWN_01,
    *TECHNOBABBLE_PATH1_01[14:],
)

TECHNOBABBLE_FACET_PATH_01 = (
    *_TECHNOBABBLE_PATH1_WITH_SPAWN,
    # Return along the same corridor without duplicating the western endpoint.
    *TECHNOBABBLE_PATH2_02[1:],
    *TECHNOBABBLE_PATH3_03,
)

# Index of the exact known spawn in the unified route.
TECHNOBABBLE_FACET_SPAWN_INDICES = (14,)


PAIN_INVERTER_PATH_01 = (
    (14323.3, 10846.0),
    (12813.3, 10172.5),
    (12706.6, 8670.7),
    (12046.3, 7170.5),
    (11401.4, 5666.6),
    (11104.1, 4165.7),
    (12380.1, 2655.5),
    (13838.0, 5496.0),
    (13645.2, 2661.5),
    (12136.8, 1741.7),
    (10629.4, 1175.4),
    (9118.9, 404.5),
    (7617.1, 708.9),
    (6114.2, 1110.0),
    (4613.7, 1104.7),
    (3324.0, 2520.8),
    (2059.3, 1018.5),
    (554.7, -202.7),
    (-947.4, -1268.4),
    (-2451.0, -1768.3),
    (-3292.4, -3271.8),
    (-4334.0, -4776.2),
    (-5233.3, -6280.5),
    (-5660.5, -7790.6),
    (-4604.2, -9290.9),
    (-4368.7, -10796.7),
    (-5871.9, -11996.5),
    (-7377.8, -11568.5),
    (-8885.3, -10854.7),
    (-9333.4, -12357.6),
    (-452.2, -13283.1),
    (371.6, -11782.2),
    (-149.9, -10277.5),
)

# Smooth Criminal: one continuous route visiting all three possible Facet spawns.
# The spawn indices are zero-based indices into this single path.  Keeping the
# three spawn coordinates inside the path avoids maintaining duplicate XY lists.
# Radiation Field / The Cipher of Dwayna
# Facet of Existence
RADIATION_FIELD_FACET_MODEL_ID = 6324
RADIATION_FIELD_FACET_PATH_01 = (
    *RADIATION_FIELD_PATH_01,
    (-5226.4, -2772.8),  # old final approach, now part of the same search path
)
# Exact intermediate spawn indices are intentionally not guessed. Detection is
# continuous over the whole route; the final approach gets the legacy reveal wait.
RADIATION_FIELD_FACET_SPAWN_INDICES = (
    len(RADIATION_FIELD_FACET_PATH_01) - 1,
)


MENTAL_BLOCK_FACET_MODEL_ID = 6323
MENTAL_BLOCK_FACET_PATH_01 = (
    (-9761.0, -8000.0),     # possible Facet spawn 1
    (7833.0, -8293.0),      # possible Facet spawn 2
    (11690.0, -6215.0),     # possible Facet spawn 3
    (15918.0, -2667.0),     # possible Facet spawn 4
)
MENTAL_BLOCK_FACET_SPAWN_INDICES = (0, 1, 2, 3)


SMOOTH_CRIMINAL_FACET_MODEL_ID = 6328
SMOOTH_CRIMINAL_FACET_PATH_01 = (
    (17024.0, -600.0),
    (18237.0, 6691.0),
    (15518.0, 8375.0),
    (13200.0, 15000.0),     # possible Facet spawn 1
    (19516.0, 4686.0),
    (12184.0, 370.0),
    (4802.0, -4990.0),
    (-8760.0, -3378.0),
    (-5555.0, -2108.0),
    (-6678.0, 6477.0),      # possible Facet spawn 2
    (-8860.0, -3178.0),
    (-11202.0, 758.0),      # possible Facet spawn 3
)
SMOOTH_CRIMINAL_FACET_SPAWN_INDICES = (3, 9, 11)


# Pain Inverter / Facet of Spirit
PAIN_INVERTER_FACET_MODEL_ID = 6326
PAIN_INVERTER_FACET_KNOWN_SPAWN_01 = (4317.0, 3352.0)

# Keep the legacy route, but explicitly pass through the observed Facet spawn.
# The spawn is inserted after the nearby (3324, 2520.8) point.
PAIN_INVERTER_FACET_PATH_01 = (
    *PAIN_INVERTER_PATH_01[:16],
    PAIN_INVERTER_FACET_KNOWN_SPAWN_01,
    *PAIN_INVERTER_PATH_01[16:],
)

PAIN_INVERTER_FACET_SPAWN_INDICES = (16,)


PREVIOUS_SKILLS_PATH_01 = (
    (-21603.1, 8285.9),
    (-21798.3, 9288.2),
    (-21789.4, 10290.0),
    (-21909.8, 11293.0),
    (-22083.2, 12295.0),
    (-21079.4, 12098.4),
    (-20077.3, 11811.3),
    (-19076.9, 11615.3),
    (-18075.5, 11247.0),
    (-17073.4, 10500.9),
    (-16247.2, 9500.6),
    (-15282.3, 8499.2),
    (-14280.3, 7593.8),
    (-13275.6, 7853.4),
    (-12272.0, 8145.0),
    (-11268.3, 8416.7),
    (-10266.5, 7814.2),
    (-9364.5, 6812.3),
    (-8361.9, 6094.6),
    (-7359.9, 6144.0),
    (-6355.5, 6385.9),
    (-5405.8, 7386.0),
    (-4936.1, 8388.2),
    (-4396.1, 9390.1),
    (-3394.9, 9932.9),
    (-2391.5, 9843.4),
    (-1391.0, 9588.0),
    (1618.8, 8503.5),
    (2311.4, 11804.0),
    (3313.1, 12027.4),
    (4316.5, 11849.2),
    (5316.6, 12024.3),
    (6318.5, 11885.3),
    (7320.1, 11537.4),
    (8321.1, 11136.9),
    (9321.7, 10593.2),
    (10324.7, 10049.8),
    (11326.2, 9505.4),
    (14718.8, 5965.5),
    (15255.1, 4964.5),
    (15921.5, 3964.5),
    (16391.0, 2962.0),
    (16474.3, 1958.2),
    (17130.1, 955.1),
    (17756.3, -45.2),
    (18257.8, -1046.1),
    (19065.4, -2046.7),
    (19437.0, -3050.3),
    (19807.5, -4051.0),
    (20178.1, -5052.2),
    (20671.6, -6054.6),
    (20041.9, -5054.5),
    (19039.5, -5913.2),
    (18158.3, -6913.3),
    (17246.3, -7913.5),
    (16287.2, -8914.5),
    (15287.1, -9047.3),
    (14284.6, -9227.9),
    (13283.0, -9408.5),
    (12281.7, -9672.8),
    (11281.3, -9987.0),
    (10280.3, -10117.4),
    (9278.4, -10264.2),
    (8278.3, -10399.0),
    (7275.8, -10447.3),
    (6274.1, -10469.4),
    (5271.4, -10193.3),
    (4270.0, -9822.4),
    (3268.8, -9567.0),
    (2265.5, -9244.4),
    (1263.1, -8930.2),
    (261.3, -8352.1),
    (-740.2, -7670.2),
    (-1556.0, -6669.4),
    (-2414.9, -5668.4),
    (-3224.1, -4665.7),
    (-4227.5, -3773.8),
)

PREVIOUS_SKILLS_PATH_02 = (
    (-11165.4, -18283.9),
    (-11328.1, -17780.3),
    (-11384.3, -17280.2),
    (-11334.4, -16778.1),
    (-11299.2, -16276.2),
    (-11329.3, -15772.8),
    (-11316.9, -15269.3),
    (-11349.1, -14767.7),
    (-11348.2, -14267.3),
    (-11384.4, -13765.5),
    (-11316.9, -13265.2),
    (-11233.8, -12765.2),
    (-11150.5, -12263.8),
    (-11067.2, -11762.9),
    (-10896.6, -11260.0),
    (-10667.6, -10758.3),
    (-10461.4, -10258.3),
    (-10254.9, -9757.7),
    (-10064.7, -9256.7),
    (-9835.3, -8756.4),
    (-9718.4, -8251.5),
    (-9640.7, -7750.0),
    (-9561.5, -7249.7),
    (-9512.5, -6749.1),
    (-9480.4, -6248.2),
    (-9458.3, -5743.9),
    (-9469.2, -5241.0),
    (-9559.7, -4740.4),
    (-9232.6, -4238.3),
    (-8888.4, -3737.5),
    (-8548.9, -3233.5),
    (-8232.0, -2729.6),
    (-8124.7, -2227.3),
    (-8145.7, -1727.3),
    (-8172.7, -1223.1),
    (-8213.0, -718.8),
    (-8263.4, -217.4),
    (-8315.9, 285.3),
    (-8388.2, 789.5),
    (-8511.6, 1292.5),
    (-8647.4, 1797.6),
    (-8766.6, 2301.6),
    (-9177.1, 2804.6),
    (-9641.8, 3305.0),
    (-9964.5, 3809.8),
    (-9928.1, 4311.3),
    (-9428.2, 4814.2),
    (-8927.0, 5191.5),
    (-8443.6, 5693.6),
    (-7941.2, 5822.0),
    (-7440.0, 5904.8),
    (-6935.2, 5990.9),
    (-6431.5, 6070.9),
    (-5925.0, 6133.0),
    (-5422.3, 6192.9),
    (-4917.6, 6210.4),
    (-4415.9, 6234.1),
    (-3914.2, 6258.1),
    (-3413.2, 6288.2),
    (-2911.0, 6320.1),
    (-2406.6, 6352.2),
    (-1902.5, 6292.1),
    (-1401.4, 6104.2),
    (-898.4, 5923.1),
    (-396.5, 5874.6),
    (107.0, 5793.2),
    (607.5, 5705.9),
    (1111.0, 5617.4),
    (1612.5, 5529.3),
    (2114.7, 5559.1),
    (2616.7, 5820.9),
    (3119.0, 6102.4),
    (3620.1, 6494.9),
    (4121.1, 6888.0),
    (4623.3, 7275.8),
    (5124.6, 7435.8),
    (5626.4, 7537.5),
    (6080.2, 7037.3),
    (6438.3, 6533.6),
    (6795.6, 6031.0),
    (7296.8, 5720.0),
    (7797.8, 5498.1),
    (8299.2, 5427.9),
    (8799.6, 5350.6),
    (9300.5, 5511.6),
    (9802.5, 5812.5),
    (10346.69, 8246.0),
    (10808.6, 6189.0),
    (11311.0, 6333.2),
    (11302.6, 5831.4),
    (11248.2, 5330.4),
    (11210.3, 4828.7),
    (11132.2, 4326.2),
    (11034.8, 3821.7),
    (10937.3, 3320.5),
    (10839.4, 2817.3),
    (10741.8, 2315.8),
    (10644.0, 1813.2),
    (10530.5, 1311.6),
    (10410.4, 807.9),
    (10264.4, 304.8),
    (10117.4, -196.6),
    (10220.3, -697.2),
    (10295.1, -1198.7),
    (9793.1, -1453.9),
    (9289.4, -1546.0),
    (8787.0, -1543.4),
    (8286.1, -1480.6),
    (7785.1, -1417.8),
    (7285.0, -1355.1),
    (6779.9, -1303.0),
    (6276.2, -1185.9),
    (5774.2, -1006.9),
    (5272.1, -1011.6),
    (4769.0, -1198.1),
    (4264.9, -1441.2),
    (3764.1, -1665.9),
    (3823.0, -2168.4),
    (4325.4, -2468.7),
    (4828.8, -2117.9),
    (5331.0, -1838.1),
    (5833.0, -1559.3),
    (6319.6, -1055.8),
    (6395.2, -554.3),
    (6346.1, -53.7),
    (6292.7, 447.5),
    (6241.4, 950.9),
    (6140.5, 1451.3),
    (6090.1, 1953.7),
    (6039.9, 2455.2),
    (5728.8, 2957.0),
    (5271.5, 3458.7),
    (4767.9, 3612.2),
    (4350.9, 3108.4),
    (3865.1, 2604.3),
    (3657.0, 2100.5),
    (3460.4, 1598.3),
    (3360.7, 1463.1),
)

PREVIOUS_SKILLS_PATH1_03 = (
    (16333.0, 13134.0),
    (15831.3, 12689.2),
    (14826.0, 12244.9),
    (13819.6, 11800.6),
    (12815.3, 11338.3),
    (12323.8, 10334.1),
    (11980.6, 9332.0),
    (10972.8, 8700.9),
    (9966.2, 8792.9),
    (8965.1, 9574.6),
    (7958.7, 10437.8),
    (7435.5, 11444.1),
    (6956.4, 12448.6),
    (6460.2, 13452.2),
    (5804.7, 14341.9),
    (4799.9, 14136.0),
    (3795.5, 13944.2),
    (2793.6, 13807.8),
    (1791.5, 13711.2),
    (787.7, 14183.2),
    (-214.4, 13677.2),
    (-737.5, 12676.2),
    (-1511.9, 11673.6),
    (-2135.2, 10670.0),
    (-2655.5, 9665.3),
    (-3659.5, 9939.1),
    (-4665.0, 9846.3),
    (-5668.2, 9829.6),
    (-6672.9, 10007.4),
    (-7178.3, 9004.0),
    (-7180.2, 8000.7),
    (-7533.2, 9006.4),
    (-8537.4, 9423.0),
    (-9538.6, 9947.0),
    (-10539.4, 10902.5),
    (-10997.0, 11906.4),
    (-10826.9, 12910.9),
    (-10739.5, 13913.7),
    (-10731.4, 14918.5),
    (-11405.8, 16127.1),
    (-12410.1, 15642.0),
    (-13412.0, 15177.1),
    (-14418.9, 14726.5),
    (-15421.4, 14567.4),
    (-16426.4, 14590.7),
    (-17430.9, 14742.7),
    (-17579.8, 13740.1),
    (-18287.3, 14623.7),
)

PREVIOUS_SKILLS_PATH2_04 = tuple(reversed(PREVIOUS_SKILLS_PATH1_03))

PREVIOUS_SKILLS_PATH3_05 = (
    (16029.7, 12397.9),
    (15026.6, 12140.9),
    (14025.6, 11883.9),
    (13371.9, 10881.3),
    (12902.8, 9874.1),
    (12694.8, 8871.6),
    (12506.1, 7866.6),
    (11497.3, 7588.6),
    (10484.8, 7371.9),
    (9480.5, 6952.3),
    (9145.1, 7044.0),
    (9620.1, 6039.9),
    (10161.9, 5033.7),
    (10405.3, 4027.2),
    (10317.9, 3024.2),
    (9724.4, 2022.1),
    (8833.3, 1015.3),
    (7832.5, 507.9),
    (6830.2, 23.6),
    (5824.7, -490.1),
    (4822.4, -1027.4),
    (3941.5, -1783.5),
    (2951.3, -2653.6),
    (2170.4, -3524.7),
    (1746.0, -4528.3),
    (1487.5, -5532.6),
    (1182.3, -6537.0),
    (1026.8, -7039.6),
)

PREVIOUS_SKILLS_PATH_06 = (
    (14323.3, 10846.0),
    (12813.3, 10172.5),
    (12706.6, 8670.7),
    (12046.3, 7170.5),
    (11401.4, 5666.6),
    (11104.1, 4165.7),
    (12380.1, 2655.5),
    (13838.0, 5496.0),
    (13645.2, 2661.5),
    (12136.8, 1741.7),
    (10629.4, 1175.4),
    (9118.9, 404.5),
    (7617.1, 708.9),
    (6114.2, 1110.0),
    (4613.7, 1104.7),
    (3324.0, 2520.8),
    (2059.3, 1018.5),
    (554.7, -202.7),
    (-947.4, -1268.4),
    (-2451.0, -1768.3),
    (-3292.4, -3271.8),
    (-4334.0, -4776.2),
    (-5233.3, -6280.5),
    (-5660.5, -7790.6),
    (-4604.2, -9290.9),
    (-4368.7, -10796.7),
    (-5871.9, -11996.5),
    (-7377.8, -11568.5),
    (-8885.3, -10854.7),
    (-9333.4, -12357.6),
    (-452.2, -13283.1),
    (371.6, -11782.2),
    (-149.9, -10277.5),
)


# ---------------------------------------------------------------------------
# Generic BottingTree helpers
# ---------------------------------------------------------------------------


def _immediate_action(name: str, fn: Callable[[], object], aftercast_ms: int = 0) -> BehaviorTree:
    def _run(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        fn()
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=name,
            action_fn=_run,
            aftercast_ms=max(0, int(aftercast_ms)),
        )
    )


def _unsupported_step(message: str) -> BehaviorTree:
    return BT.Sequence(
        name=f"Unsupported - {message}",
        children=[
            BT.LogMessage(
                message=f"Skills Unlocker BT: unsupported legacy action: {message}",
                module_name=MODULE_NAME,
            ),
            BT.Failer(name=f"Unsupported Legacy Action - {message}"),
        ],
    )


def _movement_point_steps(name: str, points: Sequence[PathPoint]) -> list[PlannerStep]:
    point_list = list(points)
    total = len(point_list)
    result: list[PlannerStep] = []
    for index, point in enumerate(point_list, start=1):
        step_name = f"{name} - Point {index:03d}/{total:03d}"
        result.append((
            step_name,
            lambda point=point: BT.Move(point, log=False),
        ))
    return result


def _facet_path_search_and_kill(
    *,
    name: str,
    model_id: int,
    path: Sequence[PathPoint],
    spawn_point_indices: Sequence[int],
    spawn_wait_ms: int = 6_000,
    kill_timeout_ms: int = 120_000,
    dead_confirm_ms: int = 2_500,
) -> BehaviorTree:
    """Follow a route until the requested Facet appears, then kill it.

    The Facet is searched by *model_id* on every tree tick, including while a
    VanquishNode waypoint is still running.  Reaching a known spawn point starts a
    short stationary reveal window because some Facets take a few seconds to
    appear when the player first reaches their hiding place.

    This node returns SUCCESS only after the matching Facet has actually been
    observed and Agent.IsDead() has remained true for ``dead_confirm_ms``.
    Reaching the end of the route without that confirmation returns FAILURE, so
    the planner can never continue to the following Resign step by mistake.
    """
    point_list = list(path)
    spawn_indices = {int(index) for index in spawn_point_indices}

    state: dict[str, object] = {
        "point_index": 0,
        "move_tree": None,
        "wait_started_ms": 0.0,
        "facet_agent_id": 0,
        "facet_seen": False,
        "facet_seen_alive": False,
        "kill_started_ms": 0.0,
        "dead_started_ms": 0.0,
        "last_target_ms": 0.0,
        "route_combat_hold": False,
        "route_clear_started_ms": 0.0,
    }

    def _reset_state() -> None:
        move_tree = state.get("move_tree")
        if isinstance(move_tree, BehaviorTree):
            try:
                move_tree.reset()
            except Exception:
                pass

        state["point_index"] = 0
        state["move_tree"] = None
        state["wait_started_ms"] = 0.0
        state["facet_agent_id"] = 0
        state["facet_seen"] = False
        state["facet_seen_alive"] = False
        state["kill_started_ms"] = 0.0
        state["dead_started_ms"] = 0.0
        state["last_target_ms"] = 0.0
        state["route_combat_hold"] = False
        state["route_clear_started_ms"] = 0.0

    def _matching_facet() -> tuple[int, bool] | None:
        """Return (agent_id, is_dead), preferring a living matching Facet."""
        dead_match: tuple[int, bool] | None = None

        try:
            enemy_ids = AgentArray.GetEnemyArray()
        except Exception:
            enemy_ids = []

        for raw_agent_id in enemy_ids:
            try:
                agent_id = int(raw_agent_id)
                if int(Agent.GetModelID(agent_id) or 0) != int(model_id):
                    continue

                is_dead = bool(Agent.IsDead(agent_id))
                if not is_dead:
                    return agent_id, False

                dead_match = (agent_id, True)
            except Exception:
                continue

        return dead_match

    def _stop_current_move() -> None:
        move_tree = state.get("move_tree")
        if isinstance(move_tree, BehaviorTree):
            try:
                move_tree.reset()
            except Exception:
                pass
        state["move_tree"] = None

        # Cancel the last click-to-move destination before HeroAI takes over.
        try:
            px, py = Player.GetXY()
            Player.Move(float(px), float(py))
        except Exception:
            pass

    def _begin_facet_combat(agent_id: int, now_ms: float) -> None:
        first_detection = not bool(state["facet_seen"])

        state["facet_seen"] = True
        state["facet_seen_alive"] = True
        state["facet_agent_id"] = int(agent_id)

        if float(state["kill_started_ms"]) <= 0.0:
            state["kill_started_ms"] = now_ms

        _stop_current_move()

        if first_detection:
            try:
                fx, fy = Agent.GetXY(agent_id)
                position_text = f" at ({float(fx):.0f}, {float(fy):.0f})"
            except Exception:
                position_text = ""

            PySystem.Console.Log(
                MODULE_NAME,
                (
                    f"{name}: Facet detected "
                    f"(model_id={model_id}, agent_id={agent_id}){position_text}. "
                    "Stopping the remaining route and waiting for confirmed death."
                ),
                PySystem.Console.MessageType.Info,
            )

    def _confirm_dead(now_ms: float) -> BehaviorTree.NodeState:
        if float(state["dead_started_ms"]) <= 0.0:
            state["dead_started_ms"] = now_ms
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    f"{name}: Facet model_id={model_id} is dead; "
                    f"confirming for {dead_confirm_ms} ms before allowing resign."
                ),
                PySystem.Console.MessageType.Info,
            )

        if now_ms - float(state["dead_started_ms"]) < float(dead_confirm_ms):
            return BehaviorTree.NodeState.RUNNING

        PySystem.Console.Log(
            MODULE_NAME,
            f"{name}: Facet death confirmed. Remaining search path skipped.",
            PySystem.Console.MessageType.Info,
        )
        _reset_state()
        return BehaviorTree.NodeState.SUCCESS

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        now_ms = time.monotonic() * 1000.0

        # ------------------------------------------------------------------
        # 1) Continuous Facet detection.  This runs even while VanquishNode runs.
        # ------------------------------------------------------------------
        match = _matching_facet()
        if match is not None:
            agent_id, is_dead = match
            state["facet_agent_id"] = int(agent_id)

            if is_dead:
                state["facet_seen"] = True
                # Seeing the matching corpse is enough to prove that the
                # objective target died, even if HeroAI killed it between ticks.
                return _confirm_dead(now_ms)

            state["dead_started_ms"] = 0.0
            if not bool(state["facet_seen_alive"]):
                _begin_facet_combat(agent_id, now_ms)
            else:
                state["facet_seen"] = True

        # ------------------------------------------------------------------
        # 2) Once seen alive, NEVER resume the search route.  Keep the Facet
        #    selected and wait specifically for its death.
        # ------------------------------------------------------------------
        if bool(state["facet_seen_alive"]):
            tracked_id = int(state["facet_agent_id"] or 0)

            if tracked_id > 0:
                try:
                    if Agent.IsDead(tracked_id):
                        return _confirm_dead(now_ms)
                except Exception:
                    # Do not interpret a missing/unreadable agent as dead.
                    # Failing is safer than resigning before proof of death.
                    pass

                if now_ms - float(state["last_target_ms"]) >= 500.0:
                    try:
                        Player.ChangeTarget(tracked_id)
                    except Exception:
                        pass
                    state["last_target_ms"] = now_ms

            if (
                float(state["kill_started_ms"]) > 0.0
                and now_ms - float(state["kill_started_ms"]) >= float(kill_timeout_ms)
            ):
                PySystem.Console.Log(
                    MODULE_NAME,
                    (
                        f"{name}: Facet was detected but its death could not be "
                        f"confirmed within {kill_timeout_ms} ms. Refusing to resign."
                    ),
                    PySystem.Console.MessageType.Error,
                )
                _reset_state()
                return BehaviorTree.NodeState.FAILURE

            return BehaviorTree.NodeState.RUNNING

        # ------------------------------------------------------------------
        # 3) Stationary reveal window at each possible spawn coordinate.
        # ------------------------------------------------------------------
        wait_started_ms = float(state["wait_started_ms"])
        if wait_started_ms > 0.0:
            if now_ms - wait_started_ms < float(spawn_wait_ms):
                return BehaviorTree.NodeState.RUNNING

            state["wait_started_ms"] = 0.0
            state["point_index"] = int(state["point_index"]) + 1

        # ------------------------------------------------------------------
        # 4) Route exhausted without seeing the Facet => FAILURE.  The planner
        #    therefore cannot advance to Resign.
        # ------------------------------------------------------------------
        point_index = int(state["point_index"])
        if point_index >= len(point_list):
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    f"{name}: completed all {len(point_list)} route points "
                    f"without confirming Facet model_id={model_id}. "
                    "Refusing to resign."
                ),
                PySystem.Console.MessageType.Error,
            )
            _reset_state()
            return BehaviorTree.NodeState.FAILURE

        # ------------------------------------------------------------------
        # 5) STRICT route combat hold.
        #
        # VanquishNode's underlying first Move pauses on COMBAT_ACTIVE, but that
        # HeroAI flag can briefly drop while a nearby enemy is still alive.
        # Add a player-centered enemy gate so the route NEVER keeps advancing
        # through an active nearby fight.
        # ------------------------------------------------------------------
        combat_active = bool(_node.blackboard.get("COMBAT_ACTIVE", False))
        nearby_enemy = False
        nearby_enemy_range = float(Range.Spellcast.value)

        try:
            px, py = Player.GetXY()
            range_sq = nearby_enemy_range * nearby_enemy_range

            for raw_enemy_id in AgentArray.GetEnemyArray():
                enemy_id = int(raw_enemy_id)
                if enemy_id <= 0:
                    continue
                if Agent.IsDead(enemy_id):
                    continue

                ex, ey = Agent.GetXY(enemy_id)
                dx = float(ex) - float(px)
                dy = float(ey) - float(py)

                if (dx * dx + dy * dy) <= range_sq:
                    nearby_enemy = True
                    break
        except Exception:
            nearby_enemy = False

        should_hold_route = combat_active or nearby_enemy

        if should_hold_route:
            if not bool(state["route_combat_hold"]):
                # Stop only once when entering the hold. Reissuing Player.Move
                # every tick would fight against HeroAI's own combat movement.
                _stop_current_move()
                state["route_combat_hold"] = True

            state["route_clear_started_ms"] = 0.0
            return BehaviorTree.NodeState.RUNNING

        if bool(state["route_combat_hold"]):
            clear_started = float(state["route_clear_started_ms"])

            if clear_started <= 0.0:
                state["route_clear_started_ms"] = now_ms
                return BehaviorTree.NodeState.RUNNING

            # Require a stable clear window before recreating VanquishNode and
            # resuming the exact same waypoint.
            if now_ms - clear_started < 750.0:
                return BehaviorTree.NodeState.RUNNING

            state["route_combat_hold"] = False
            state["route_clear_started_ms"] = 0.0
            state["move_tree"] = None

        # ------------------------------------------------------------------
        # 6) Tick one combat-aware VanquishNode waypoint.
        #
        #    Do NOT use BT.Move here: Move can resume/continue movement while
        #    enemies are still present.  VanquishNode wraps MoveAndKill and
        #    therefore advances through the search route while clearing combat
        #    around every waypoint.
        # ------------------------------------------------------------------
        move_tree = state.get("move_tree")
        if not isinstance(move_tree, BehaviorTree):
            point = point_list[point_index]
            move_tree = BT.VanquishNode(
                steps=[point],
                pause_on_combat=True,
                flag_heroes_to_waypoint=False,
                name=f"{name} - Facet Search Point {point_index + 1:03d}/{len(point_list):03d}",
                log=False,
            )
            state["move_tree"] = move_tree

        move_result = move_tree.tick()

        if move_result == BehaviorTree.NodeState.FAILURE:
            PySystem.Console.Log(
                MODULE_NAME,
                f"{name}: movement failed at route point {point_index + 1}/{len(point_list)}.",
                PySystem.Console.MessageType.Error,
            )
            _reset_state()
            return BehaviorTree.NodeState.FAILURE

        if move_result == BehaviorTree.NodeState.RUNNING:
            return BehaviorTree.NodeState.RUNNING

        # Waypoint reached.  Known Facet positions get a stationary reveal wait.
        try:
            move_tree.reset()
        except Exception:
            pass
        state["move_tree"] = None

        if point_index in spawn_indices:
            state["wait_started_ms"] = now_ms
            return BehaviorTree.NodeState.RUNNING

        state["point_index"] = point_index + 1
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"{name} - Search And Kill Facet {model_id}",
            action_fn=_tick,
        )
    )


def _winds_add_heroes_with_builds() -> BehaviorTree:
    # Exact legacy order: leave party, add Gwen/Vekk/Ogden, then load their bars.
    return BT.Sequence(
        name="Winds - Add Heroes And Builds",
        children=[
            BT.LeaveParty(),
            BT.Wait(1_000),
            _immediate_action("Add Gwen", lambda: GLOBAL_CACHE.Party.Heroes.AddHero(24), 250),
            _immediate_action("Add Vekk", lambda: GLOBAL_CACHE.Party.Heroes.AddHero(26), 250),
            _immediate_action("Add Ogden", lambda: GLOBAL_CACHE.Party.Heroes.AddHero(27), 250),
            BT.Wait(1_200),
            BT.LoadHeroSkillbar(1, "OQhkAsC8gFKCNkDT/QY6yQGcxA", log=True),
            BT.Wait(600),
            BT.LoadHeroSkillbar(2, "OgljgwMpZO0iwBgWp5N0h14dMA", log=True),
            BT.Wait(600),
            BT.LoadHeroSkillbar(3, "OwUTMwHD1ZMWP0iBkZSPIDsSAA", log=True),
            BT.Wait(600),
        ],
    )


def _winds_add_henchies() -> BehaviorTree:
    children: list[BehaviorTree] = []
    for henchman_id in range(1, 8):
        children.append(
            _immediate_action(
                f"Add Henchman {henchman_id}",
                lambda henchman_id=henchman_id: GLOBAL_CACHE.Party.Henchmen.AddHenchman(henchman_id),
                250,
            )
        )
    return BT.Sequence(name="Winds - Add Henchmen", children=children)


IAU_SKILLBAR_BY_PROFESSION = {
    "Dervish": "OgSCU8pkcQZwnwWIAAAAAAAA",
    "Ritualist": "OASjUwHKIRyBlBfCbhAAAAAAAAA",
    "Warrior": "OQQTU4DHHaLUOoM4TAAAAAAAAAA",
    "Ranger": "OgQTU4DfHaLUOoM4TAAAAAAAAAA",
    "Necromancer": "OApCU8pkcQZwnwWIAAAAAAAA",
    "Elementalist": "OgRDU8x8QbhyBlBfCAAAAAAAAA",
    "Mesmer": "OQRDATxHTbhyBlBfCAAAAAAAAA",
    "Monk": "OwQTU4DDHaLUOoM4TAAAAAAAAAA",
    # The legacy script used the typo "Assasin". Keep the same template for the
    # actual profession name too so the BT conversion works on Assassin characters.
    "Assasin": "OwRjUwH84QbhyBlBfCAAAAAAAAA",
    "Assassin": "OwRjUwH84QbhyBlBfCAAAAAAAAA",
    "Paragon": "OQSCU8pkcQZwnwWIAAAAAAAA",
}


def _iau_equip_skillbar() -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        profession, _ = Agent.GetProfessionNames(Player.GetAgentID())
        template = IAU_SKILLBAR_BY_PROFESSION.get(str(profession), "")
        if not template:
            return BT.Failer(name=f"No Cold As Ice build for {profession}")
        return BT.LoadSkillbar(template=template, log=True)

    return BT.Subtree(name="Equip Cold As Ice Skillbar", subtree_fn=_build)


def _configure_botting_tree(tree: BottingTree) -> None:
    tree.Config.ConfigureUpkeep(
        looting_enabled=True,
        resurrection_scroll=False,
        auto_inventory_handler_enabled=False,
        enable_party_wipe_recovery=True,
        enable_nearest_shrine_recovery=False,
        heroai_state_logging=False,
    )
    # The legacy bot kept HeroAI active globally. Configure it directly so a
    # checkpoint jump does not depend on replaying a setup step first.
    tree.SetMultiAccount(True)
    tree.SetIsolationEnabled(False)
    tree.SetHeadlessHeroAIEnabled(True, reset_runtime=False)
    tree.pause_on_combat = True



# ---------------------------------------------------------------------------
# Polymock runtime used by the four Asura summon skill unlocks
# ---------------------------------------------------------------------------

# Quiet mode: keep errors / real failures, suppress flow/debug spam.
POLYMOCK_VERBOSE_LOGS = False
BT_FLOW_LOGS = False

def _trace_log(module_name: str, message: str, *args, **kwargs) -> None:
    if POLYMOCK_VERBOSE_LOGS:
        ConsoleLog(module_name, message, *args, **kwargs)


POLYMOCK_MAP_TIMEOUT_MS = 45_000
POST_LOAD_WAIT_MS = 1_000

RATA_SUM_MAP_ID = 640
POLYMOCK_ARENA_MAP_IDS = (686, 687, 688)

POLYMOCK_HOFF_POS = Vec2f(15933.00, 19115.00)
POLYMOCK_REGISTER_POS = Vec2f(15506.00, 18910.00)
POLYMOCK_SELECTION_POS = Vec2f(4185.00, 44.00)
FONK_SELECTION_POS = Vec2f(-167.00, -9.00)
DUNE_SELECTION_POS = Vec2f(3333.00, 368.00)
GRULHAMMER_SELECTION_POS = Vec2f(-167.00, -9.00)
VOLUMANDUS_LAUNCH_POS = Vec2f(4185.00, 44.00)
HOFF_SELECTOR_NAME = "Wokk"

YULMA_POS = Vec2f(19231.00, 19669.00)
PLURGG_POS = Vec2f(16382.00, 17753.00)
BLARP_POS = Vec2f(-8940.00, -21799.00)
FONK_POS = Vec2f(19789.00, -3760.00)
DUNE_TEARDRINKER_POS = Vec2f(-13317.00, 15435.00)
GRULHAMMER_POS = Vec2f(-22492.00, 13722.00)
VOLUMANDUS_POS = Vec2f(23229.00, -12794.00)

DUNE_OUTPOST_NAME = "Doomlore Shrine"   # Sanctuaire de la Legende funeste
GRULHAMMER_OUTPOST_NAME = "Umbral Grotto"   # Grotte obscure
VOLUMANDUS_OUTPOST_NAME = "Tarnished Haven"   # Havre terni

# Quest IDs from Sources/frenkeyLib/Polymock/data.py
YULMA_QUEST_ID = 882
PLURGG_QUEST_ID = 875
BLARP_QUEST_ID = 881
FONK_QUEST_ID = 876
DUNE_TEARDRINKER_QUEST_ID = 877
GRULHAMMER_QUEST_ID = 878
VOLUMANDUS_QUEST_ID = 879
HOFF_QUEST_ID = 880

# Quest accept / reward dialogs supplied during testing.
YULMA_ACCEPT_DIALOG = 0x837201
YULMA_REWARD_DIALOG = 0x837207

PLURGG_ACCEPT_DIALOG = 0x836B01
PLURGG_REWARD_DIALOG = 0x836B07

BLARP_ACCEPT_DIALOG = 0x837101
BLARP_REWARD_DIALOG = 0x837107

FONK_ACCEPT_DIALOG = 0x836C01
DUNE_TEARDRINKER_ACCEPT_DIALOG = 0x836D01
GRULHAMMER_ACCEPT_DIALOG = 0x836E01
VOLUMANDUS_ACCEPT_DIALOG = 0x836F01
HOFF_ACCEPT_DIALOG = 0x837001
HOFF_START_DIALOG = 0x84
HOFF_REWARD_DIALOG = 0x837007
FONK_REWARD_DIALOG = 0x836C07
DUNE_TEARDRINKER_REWARD_DIALOG = 0x836D07
GRULHAMMER_REWARD_DIALOG = 0x836E07
VOLUMANDUS_REWARD_DIALOG = 0x836F07

# Registration dialogs.
REGISTER_STARTER_1 = 0x185
REGISTER_STARTER_2 = 0x385
REGISTER_STARTER_3 = 0x485
REGISTER_FIRE_IMP = 0x85
REGISTER_KAPPA = 0x985
REGISTER_ICE_IMP = 0x285
REGISTER_EARTH_ELEMENTAL = 0x685
REGISTER_FIRE_ELEMENTAL = 0x785
REGISTER_ICE_ELEMENTAL = 0x885
REGISTER_ALOE_SEED = 0x585

# Polymock dialogs.
#
# xx85 = select one of the THREE pieces registered for the whole match.
# xx86 = select the ACTIVE piece for the current round.
MATCH_FIRE_IMP = 0x2285
MATCH_FIRE_ELEMENTAL = 0x2185
MATCH_ICE_IMP = 0x2785
MATCH_ICE_ELEMENTAL = 0x2685
MATCH_EARTH_ELEMENTAL = 0x2085
MATCH_GARGOYLE = 0x2485
MATCH_KAPPA = 0x2885
MATCH_MERGOYLE = 0x2A85
MATCH_NAGA_SHAMAN = 0x2D85
MATCH_SKALE = 0x2E85
MATCH_STONE_RAIN = 0x2F85

ROUND_FIRE_IMP = 0x2286
ROUND_FIRE_ELEMENTAL = 0x2186
ROUND_ICE_IMP = 0x2786
ROUND_ICE_ELEMENTAL = 0x2686
ROUND_EARTH_ELEMENTAL = 0x2086
ROUND_ALOE_SEED = 0x1E86
ROUND_GARGOYLE = 0x2486
ROUND_KAPPA = 0x2886
ROUND_MERGOYLE = 0x2A86
ROUND_NAGA_SHAMAN = 0x2D86
ROUND_SKALE = 0x2E86
ROUND_STONE_RAIN = 0x2F86

START_MATCH_DIALOG = 0x87

# Round order used after one of OUR pieces dies.
# The first entry is also the piece used for round 1.
ROUND_DIALOGS_BY_QUEST_ID: dict[int, tuple[int, int, int]] = {
    YULMA_QUEST_ID: (
        ROUND_GARGOYLE,
        ROUND_MERGOYLE,
        ROUND_SKALE,
    ),
    PLURGG_QUEST_ID: (
        ROUND_SKALE,
        ROUND_FIRE_IMP,
        ROUND_GARGOYLE,
    ),
    BLARP_QUEST_ID: (
        ROUND_KAPPA,
        ROUND_FIRE_IMP,
        ROUND_SKALE,
    ),
    FONK_QUEST_ID: (
        ROUND_GARGOYLE,
        ROUND_KAPPA,
        ROUND_FIRE_IMP,
    ),
    DUNE_TEARDRINKER_QUEST_ID: (
        ROUND_EARTH_ELEMENTAL,
        ROUND_FIRE_IMP,
        ROUND_KAPPA,
    ),
    GRULHAMMER_QUEST_ID: (
        ROUND_KAPPA,
        ROUND_EARTH_ELEMENTAL,
        ROUND_ICE_IMP,
    ),
    VOLUMANDUS_QUEST_ID: (
        ROUND_EARTH_ELEMENTAL,
        ROUND_FIRE_ELEMENTAL,
        ROUND_KAPPA,
    ),
    HOFF_QUEST_ID: (
        ROUND_ICE_ELEMENTAL,
        ROUND_EARTH_ELEMENTAL,
        ROUND_FIRE_ELEMENTAL,
    ),
}

LAST_THREE_OPPONENT_DATA = {
    DUNE_TEARDRINKER_QUEST_ID: {
        "label": "Dune Teardrinker",
        "outpost": DUNE_OUTPOST_NAME,
        "opponent_pos": DUNE_TEARDRINKER_POS,
        "accept_dialog": DUNE_TEARDRINKER_ACCEPT_DIALOG,
        "reward_dialog": DUNE_TEARDRINKER_REWARD_DIALOG,
        "selector_pos": DUNE_SELECTION_POS,
        "match_dialogs": (
            MATCH_EARTH_ELEMENTAL,
            MATCH_FIRE_IMP,
            MATCH_KAPPA,
        ),
        "first_round_dialog": ROUND_EARTH_ELEMENTAL,
    },
    GRULHAMMER_QUEST_ID: {
        "label": "Grulhammer",
        "outpost": GRULHAMMER_OUTPOST_NAME,
        "opponent_pos": GRULHAMMER_POS,
        "accept_dialog": GRULHAMMER_ACCEPT_DIALOG,
        "reward_dialog": GRULHAMMER_REWARD_DIALOG,
        "selector_pos": GRULHAMMER_SELECTION_POS,
        "match_dialogs": (
            MATCH_KAPPA,
            MATCH_EARTH_ELEMENTAL,
            MATCH_ICE_IMP,
        ),
        "first_round_dialog": ROUND_KAPPA,
    },
    VOLUMANDUS_QUEST_ID: {
        "label": "Volumandus",
        "outpost": VOLUMANDUS_OUTPOST_NAME,
        "opponent_pos": VOLUMANDUS_POS,
        "accept_dialog": VOLUMANDUS_ACCEPT_DIALOG,
        "reward_dialog": VOLUMANDUS_REWARD_DIALOG,
        "selector_pos": VOLUMANDUS_LAUNCH_POS,
        "match_dialogs": (
            MATCH_EARTH_ELEMENTAL,
            MATCH_FIRE_ELEMENTAL,
            MATCH_KAPPA,
        ),
        "first_round_dialog": ROUND_EARTH_ELEMENTAL,
    },
}


def _selection_pos_for_quest(quest_id: int) -> Vec2f:
    quest_id = int(quest_id)
    if quest_id == FONK_QUEST_ID:
        return FONK_SELECTION_POS
    if quest_id == DUNE_TEARDRINKER_QUEST_ID:
        return DUNE_SELECTION_POS
    if quest_id == GRULHAMMER_QUEST_ID:
        return GRULHAMMER_SELECTION_POS
    if quest_id == VOLUMANDUS_QUEST_ID:
        return VOLUMANDUS_LAUNCH_POS
    return POLYMOCK_SELECTION_POS

# =============================================================================
# Polymock combat patch
# =============================================================================

widget_state = state.WidgetState()
widget_state.debug = False

combat_handler = combat.Combat()
combat_handler.state.debug = False

_last_piece_signature: tuple[int, int, int] | None = None
_last_combat_tick = 0.0
_last_diag_tick = 0.0

# Explicit quest context set by each Polymock attempt. WidgetState arena
# auto-detection is not reliable enough to drive combat on its own.
_polymock_forced_quest_id: int | None = None
_polymock_runtime_active = False
_polymock_saved_pause_on_combat: bool | None = None

# Round manager runtime.
_round_quest_id: int | None = None
_round_next_piece_index = 1  # index 0 is the piece selected for round 1
_round_had_active_piece = False
_round_piece_was_dead = False
_round_missing_bar_since: float | None = None
_round_pending_dialog: int | None = None

# Direct between-round state machine.
_round_phase = "idle"
_round_phase_started = 0.0
_round_npc_id = 0
_round_retry_count = 0
_round_last_wait_log = 0.0


def _current_piece_signature() -> tuple[int, int, int]:
    result: list[int] = []
    for slot in (1, 2, 3):
        try:
            skill = GLOBAL_CACHE.SkillBar.GetSkillData(slot)
            result.append(int(skill.id.id) if skill and skill.id.id > 0 else 0)
        except Exception:
            result.append(0)
    return tuple(result)  # type: ignore[return-value]



def _current_full_bar_signature() -> tuple[int, ...]:
    result: list[int] = []
    for slot in range(1, 9):
        try:
            skill = GLOBAL_CACHE.SkillBar.GetSkillData(slot)
            result.append(int(skill.id.id) if skill and skill.id.id > 0 else 0)
        except Exception:
            result.append(0)
    return tuple(result)


def _polymock_common_ids() -> tuple[int, int, int, int, int]:
    return (
        int(GLOBAL_CACHE.Skill.GetID("Polymock_Power_Drain")),
        int(GLOBAL_CACHE.Skill.GetID("Polymock_Block")),
        int(GLOBAL_CACHE.Skill.GetID("Polymock_Glyph_of_Concentration")),
        int(GLOBAL_CACHE.Skill.GetID("Polymock_Ether_Signet")),
        int(GLOBAL_CACHE.Skill.GetID("Polymock_Glyph_of_Power")),
    )


def _is_polymock_bar_active() -> bool:
    """
    TRUE only for an actual transformed Polymock bar.

    The previous diagnostic considered any non-empty slots 1-3 to be Polymock,
    which incorrectly treated the player's normal profession bar as a piece.
    """
    if int(Map.GetMapID() or 0) not in POLYMOCK_ARENA_MAP_IDS:
        return False

    bar = _current_full_bar_signature()
    common = _polymock_common_ids()

    if not all(common):
        return False

    # Real Polymock bars have the five common skills in slots 4..8.
    if tuple(bar[3:8]) != common:
        return False

    # And at least one piece-specific damage skill in slots 1..3.
    return any(bar[0:3])


def _get_polymock_quest_by_id(quest_id: int):
    for quest_entry in Polymock_Quests:
        if int(quest_entry.value.quest_id) == int(quest_id):
            return quest_entry.value
    return None


def _inject_forced_quest_if_needed() -> None:
    """Keep combat.py pinned to the quest explicitly launched by the planner."""
    forced_id = int(_polymock_forced_quest_id or 0)
    if forced_id <= 0:
        return

    current_id = int(getattr(getattr(widget_state, "quest", None), "quest_id", 0) or 0)
    if current_id == forced_id:
        return

    forced_quest = _get_polymock_quest_by_id(forced_id)
    if forced_quest is not None:
        widget_state.quest = forced_quest


def _skill_debug(slot: int) -> str:
    try:
        skill = GLOBAL_CACHE.SkillBar.GetSkillData(slot)
        if not skill or skill.id.id <= 0:
            return f"{slot}:EMPTY"

        sid = int(skill.id.id)
        name = GLOBAL_CACHE.Skill.GetName(sid) or str(sid)
        recharge_raw = int(getattr(skill, "recharge", 0) or 0)
        ready = recharge_raw == 0

        try:
            energy_cost = float(
                Routines.Checks.Skills.GetEnergyCostWithEffects(
                    sid,
                    int(Player.GetAgentID() or 0),
                )
            )
        except Exception:
            try:
                energy_cost = float(GLOBAL_CACHE.Skill.Data.GetEnergyCost(sid))
            except Exception:
                energy_cost = -1.0

        return (
            f"{slot}:{name}"
            f"[id={sid},ready={ready},recharge={recharge_raw},e={energy_cost:g}]"
        )
    except Exception as exc:
        return f"{slot}:ERR({type(exc).__name__})"


def _diagnostic_tick() -> None:
    global _last_diag_tick

    now = time.monotonic()
    if now - _last_diag_tick < 1.0:
        return
    _last_diag_tick = now

    map_id = int(Map.GetMapID() or 0)
    if map_id not in POLYMOCK_ARENA_MAP_IDS:
        return

    player_id = int(Player.GetAgentID() or 0)

    try:
        hp_frac = float(Agent.GetHealth(player_id)) if player_id > 0 else -1.0
    except Exception:
        hp_frac = -1.0

    try:
        max_hp = float(Agent.GetMaxHealth(player_id)) if player_id > 0 else 0.0
    except Exception:
        max_hp = 0.0

    try:
        energy_frac = float(Agent.GetEnergy(player_id)) if player_id > 0 else -1.0
        max_energy = float(Agent.GetMaxEnergy(player_id)) if player_id > 0 else 0.0
        energy = energy_frac * max_energy
    except Exception:
        max_energy = 0.0
        energy = -1.0

    quest = getattr(widget_state, "quest", None)
    quest_id = int(getattr(quest, "quest_id", 0) or 0)

    target_id = int(getattr(combat_handler, "target_id", 0) or 0)
    try:
        target_hp_frac = float(Agent.GetHealth(target_id)) if target_id > 0 else -1.0
    except Exception:
        target_hp_frac = -1.0

    try:
        target_cast = int(Agent.GetCastingSkillID(target_id)) if target_id > 0 else 0
    except Exception:
        target_cast = 0

    _trace_log(
        MODULE_NAME,
        (
            "[DIAG] "
            f"map={map_id} quest={quest_id} forced={_polymock_forced_quest_id} "
            f"hp={hp_frac:.3f}/{max_hp:.0f} energy={energy:.1f}/{max_energy:.0f} "
            f"piece={_current_piece_signature()} polymock={_is_polymock_bar_active()} "
            f"target={target_id} thp={target_hp_frac:.3f} cast={target_cast} "
            f"round_phase={_round_phase} next_idx={_round_next_piece_index} "
            f"pending={_round_pending_dialog}"
        ),
    )

    _trace_log(
        MODULE_NAME,
        "[DIAG BAR] " + " | ".join(_skill_debug(slot) for slot in range(1, 9)),
    )



def _has_effect(skill_name: str) -> bool:
    try:
        skill_id = int(GLOBAL_CACHE.Skill.GetID(skill_name))
        if skill_id <= 0 or combat_handler.player_id <= 0:
            return False
        return bool(
            GLOBAL_CACHE.Effects.BuffExists(combat_handler.player_id, skill_id)
            or GLOBAL_CACHE.Effects.EffectExists(combat_handler.player_id, skill_id)
        )
    except Exception:
        return False


def _reset_round_manager() -> None:
    global _round_quest_id
    global _round_next_piece_index
    global _round_had_active_piece
    global _round_piece_was_dead
    global _round_missing_bar_since
    global _round_pending_dialog
    global _round_phase
    global _round_phase_started
    global _round_npc_id
    global _round_retry_count
    global _round_last_wait_log

    _round_quest_id = None
    _round_next_piece_index = 1
    _round_had_active_piece = False
    _round_piece_was_dead = False
    _round_missing_bar_since = None
    _round_pending_dialog = None

    _round_phase = "idle"
    _round_phase_started = 0.0
    _round_npc_id = 0
    _round_retry_count = 0
    _round_last_wait_log = 0.0


def _start_next_round_piece_selection(dialog_id: int) -> None:
    global _round_pending_dialog
    global _round_phase
    global _round_phase_started
    global _round_npc_id
    global _round_retry_count

    _round_pending_dialog = int(dialog_id)
    _round_phase = "find_npc"
    _round_phase_started = time.monotonic()
    _round_npc_id = 0
    _round_retry_count = 0

    _trace_log(
        MODULE_NAME,
        (
            f"[ROUND] Need next piece: 0x{dialog_id:X}. "
            "Waiting for selector NPC."
        ),
    )


def _tick_round_selection_state_machine(now: float) -> bool:
    """
    Return True while a between-round selection is in progress.

    This deliberately avoids a nested MoveAndDialog BehaviorTree.  The live log
    showed that nested tree stalling after movement.  Here every action is sent
    directly and logged.
    """
    global _round_phase
    global _round_phase_started
    global _round_npc_id
    global _round_pending_dialog
    global _round_retry_count
    global _round_last_wait_log
    global _round_next_piece_index
    global _round_piece_was_dead
    global _round_missing_bar_since

    if _round_pending_dialog is None:
        return False

    # IMPORTANT:
    # Selecting xx86 transforms the player immediately, BEFORE the round is
    # actually started.  Do NOT treat the new Polymock bar as success yet.
    # We must always continue through wait_start and send 0x87 first.
    if _round_phase == "wait_transform" and _is_polymock_bar_active():
        _trace_log(
            MODULE_NAME,
            (
                f"[ROUND] New Polymock bar confirmed after 0x87 "
                f"(piece dialog 0x{_round_pending_dialog:X}); round ready."
            ),
        )
        _round_next_piece_index += 1
        _round_pending_dialog = None
        _round_phase = "idle"
        _round_phase_started = 0.0
        _round_npc_id = 0
        _round_retry_count = 0
        _round_piece_was_dead = False
        _round_missing_bar_since = None
        combat_handler.opener_used = False
        return False

    if _round_phase == "find_npc":
        quest_id = int(_round_quest_id or 0)

        try:
            if quest_id == HOFF_QUEST_ID:
                # Hoff's arena layout varies between generated instances.
                # Resolve Wokk by name instead of using a fixed selector XY.
                npc_id = int(Agent.GetAgentIDByName(HOFF_SELECTOR_NAME) or 0)
            else:
                selector_pos = _selection_pos_for_quest(quest_id)
                npc_id = int(
                    RoutinesAgents.GetNearestNPCXY(
                        selector_pos.x,
                        selector_pos.y,
                        350.0,
                    )
                    or 0
                )
        except Exception as exc:
            npc_id = 0
            if now - _round_last_wait_log >= 1.0:
                _round_last_wait_log = now
                _trace_log(
                    MODULE_NAME,
                    f"[ROUND] NPC lookup exception: {type(exc).__name__}: {exc}",
                )

        if npc_id <= 0:
            if now - _round_last_wait_log >= 1.0:
                _round_last_wait_log = now
                if quest_id == HOFF_QUEST_ID:
                    _trace_log(
                        MODULE_NAME,
                        f"[ROUND] Selector NPC '{HOFF_SELECTOR_NAME}' not available yet; waiting...",
                    )
                else:
                    selector_pos = _selection_pos_for_quest(quest_id)
                    _trace_log(
                        MODULE_NAME,
                        (
                            f"[ROUND] Selector NPC not available yet near "
                            f"({selector_pos.x:.0f}, {selector_pos.y:.0f}); waiting..."
                        ),
                    )
            return True

        _round_npc_id = npc_id
        Player.ChangeTarget(npc_id)
        _round_phase = "wait_target"
        _round_phase_started = now
        _trace_log(
            MODULE_NAME,
            f"[ROUND] Selector NPC found: agent {npc_id}; targeting.",
        )
        return True

    if _round_phase == "wait_target":
        if Player.GetTargetID() != _round_npc_id:
            if now - _round_phase_started >= 0.25:
                Player.ChangeTarget(_round_npc_id)
                _round_phase_started = now
            return True

        Player.Interact(_round_npc_id, False)
        _round_phase = "wait_piece_dialog"
        _round_phase_started = now
        _trace_log(
            MODULE_NAME,
            f"[ROUND] Interacted with selector NPC {_round_npc_id}.",
        )
        return True

    if _round_phase == "wait_piece_dialog":
        if now - _round_phase_started < 0.45:
            return True

        Player.SendDialog(_round_pending_dialog)
        _round_phase = "wait_start"
        _round_phase_started = now
        _trace_log(
            MODULE_NAME,
            f"[ROUND] Sent piece dialog 0x{_round_pending_dialog:X}.",
        )
        return True

    if _round_phase == "wait_start":
        if now - _round_phase_started < 0.55:
            return True

        Player.SendDialog(START_MATCH_DIALOG)
        _round_phase = "wait_transform"
        _round_phase_started = now
        _trace_log(
            MODULE_NAME,
            "[ROUND] Sent 0x87; waiting for new transformation.",
        )
        return True

    if _round_phase == "wait_transform":
        # Success is checked near the top of this function, but ONLY in this
        # phase, which guarantees 0x87 has already been sent.
        if now - _round_phase_started < 3.0:
            return True

        _round_retry_count += 1
        _trace_log(
            MODULE_NAME,
            (
                f"[ROUND] No transformation after 3s; retry "
                f"#{_round_retry_count} from NPC interaction."
            ),
        )

        # Retry from scratch; do not consume the next roster index until
        # a real Polymock bar appears.
        _round_phase = "find_npc"
        _round_phase_started = now
        _round_npc_id = 0
        return True

    # Defensive recovery.
    _round_phase = "find_npc"
    _round_phase_started = now
    return True


def _tick_polymock_round_manager() -> bool:
    """
    Return True only when Combat.Fight() is allowed to control skills.

    The round manager remains dormant until a REAL Polymock bar (slots 4..8
    equal the common Polymock skills) has appeared at least once.
    """
    global _round_quest_id
    global _round_next_piece_index
    global _round_had_active_piece
    global _round_piece_was_dead
    global _round_missing_bar_since

    current_map_id = int(Map.GetMapID() or 0)
    if current_map_id not in POLYMOCK_ARENA_MAP_IDS:
        _reset_round_manager()
        return False

    quest = getattr(widget_state, "quest", None)
    quest_id = int(getattr(quest, "quest_id", 0) or 0)
    if quest_id not in ROUND_DIALOGS_BY_QUEST_ID:
        return False

    if _round_quest_id != quest_id:
        _round_quest_id = quest_id
        _round_next_piece_index = 1
        _round_had_active_piece = False
        _round_piece_was_dead = False
        _round_missing_bar_since = None
        _trace_log(
            MODULE_NAME,
            f"[ROUND] New match state for quest={quest_id}.",
        )

    now = time.monotonic()

    # A between-round selector sequence has absolute priority over combat.
    if _round_pending_dialog is not None:
        _tick_round_selection_state_machine(now)
        return False

    active_bar = _is_polymock_bar_active()

    # Do not start death tracking from the normal character bar.
    if not _round_had_active_piece:
        if active_bar:
            _round_had_active_piece = True
            _round_piece_was_dead = False
            _round_missing_bar_since = None
            combat_handler.opener_used = False
            _trace_log(
                MODULE_NAME,
                (
                    "[ROUND] First REAL Polymock piece detected; "
                    "round tracking armed."
                ),
            )
            return True

        return False

    if active_bar:
        _round_piece_was_dead = False
        _round_missing_bar_since = None
        return True

    # Real Polymock bar has disappeared after a round was active.
    if _round_missing_bar_since is None:
        _round_missing_bar_since = now
        _trace_log(
            MODULE_NAME,
            "[ROUND] Polymock bar disappeared; confirming piece loss...",
        )
        return False

    if now - _round_missing_bar_since < 0.35:
        return False

    if not _round_piece_was_dead:
        _round_piece_was_dead = True
        combat_handler.opener_used = False
        _trace_log(
            MODULE_NAME,
            "[ROUND] Our active Polymock piece is lost.",
        )

    round_dialogs = ROUND_DIALOGS_BY_QUEST_ID[quest_id]

    if _round_next_piece_index >= len(round_dialogs):
        # All three player pieces are gone.  GW will return us to the outpost.
        _trace_log(
            MODULE_NAME,
            "[ROUND] No player pieces remaining; waiting for match return.",
        )
        return False

    next_dialog = int(round_dialogs[_round_next_piece_index])
    _start_next_round_piece_selection(next_dialog)
    return False



def _damage_skill_meta(skill_id: int):
    """Resolve the current damage skill from ANY known Polymock piece."""
    for piece in PolymockPieces:
        for _slot, skill in piece.value.damage_skills.items():
            if int(skill.skill_id) == int(skill_id):
                return skill
    return None


def _patched_use_polymock_damage_skills(self) -> bool:
    """
    Diagnostic combat policy.

    Damage:
      3 -> 2 -> 1 whenever actually ready/affordable.

    Utility:
      4/5 remain reactive in Combat.Fight().
      5 is NOT spammed proactively (prevents wasting energy).
      6 is used only before a damage skill flagged for Concentration,
        and only if there is enough energy for glyph + attack.
      7 remains the original emergency Ether Signet at ~0 Energy.
      8 remains a low-HP Glyph of Power.
    """
    # Damage can still run generically even if quest auto-detection fails.
    # Reactive slots 4/5 use quest metadata when available.
    if self.remove_block:
        candidate_slots = [1]
    else:
        candidate_slots = [3, 2, 1]

    # Low HP utility. Don't cast if doing so would leave no usable attack.
    if (
        self.player_hp_percent <= 50.0
        and self.IsSkillReady(8)
        and not _has_effect("Polymock_Glyph_of_Power")
    ):
        # Keep at least a little energy headroom where possible.
        if self.player_energy >= 5.0:
            _trace_log(
                MODULE_NAME,
                f"[COMBAT] HP={self.player_hp_percent:.1f}% -> using slot 8.",
            )
            if self.UseSkill(8, self.player_id):
                return True

    for skill_slot in candidate_slots:
        skill = self.skills.get(skill_slot)
        if not skill:
            continue

        sid = int(skill.id.id)
        meta = _damage_skill_meta(sid)

        if not self.IsSkillReady(skill_slot):
            continue

        should_use_concentration = bool(
            meta is not None
            and getattr(meta, "use_glyph_of_concentration", False)
        )

        if should_use_concentration and not _has_effect("Polymock_Glyph_of_Concentration"):
            try:
                attack_cost = float(
                    Routines.Checks.Skills.GetEnergyCostWithEffects(
                        sid,
                        self.player_id,
                    )
                )
                glyph_id = int(
                    GLOBAL_CACHE.Skill.GetID("Polymock_Glyph_of_Concentration")
                )
                glyph_cost = float(
                    Routines.Checks.Skills.GetEnergyCostWithEffects(
                        glyph_id,
                        self.player_id,
                    )
                )
            except Exception:
                attack_cost = 0.0
                glyph_cost = 0.0

            if (
                self.IsSkillReady(6)
                and self.player_energy >= (attack_cost + glyph_cost)
            ):
                _trace_log(
                    MODULE_NAME,
                    (
                        f"[COMBAT] slot {skill_slot} wants Concentration; "
                        f"energy={self.player_energy:.1f}, need={attack_cost + glyph_cost:.1f} -> slot 6."
                    ),
                )
                if self.UseSkill(6, self.player_id):
                    return True

        _trace_log(
            MODULE_NAME,
            (
                f"[COMBAT] using damage slot {skill_slot}: "
                f"{GLOBAL_CACHE.Skill.GetName(sid)} "
                f"(energy={self.player_energy:.1f})"
            ),
        )
        self.opener_used = True

        if self.UseSkill(skill_slot, self.target_id):
            return True

    return False


def _patched_block_skill(self, skill_id: int = 0) -> bool:
    """
    Polymock Block is a self-protection enchantment.
    The original module sends slot 5 using target_id (the opponent).
    """
    slot = 5
    if not self.IsSkillReady(slot):
        return False

    if skill_id:
        self.state.Log(
            f"Trying to block {GLOBAL_CACHE.Skill.GetName(skill_id)}."
        )

    return bool(self.UseSkill(slot, self.player_id))


# Patch only this script process; repo files are not modified.
combat_handler.UsePolymock_Damage_Skills = (
    _patched_use_polymock_damage_skills.__get__(combat_handler, type(combat_handler))
)
combat_handler.BlockSkill = (
    _patched_block_skill.__get__(combat_handler, type(combat_handler))
)




def _set_polymock_runtime(quest_id: int | None, active: bool) -> None:
    """Scope custom Polymock combat without changing the Skill Unlocker's global HeroAI policy."""
    global _polymock_runtime_active
    global _polymock_forced_quest_id
    global _polymock_saved_pause_on_combat
    global _last_piece_signature

    tree = ensure_botting_tree()

    if active:
        requested_id = int(quest_id or 0)
        if requested_id <= 0:
            raise ValueError("Polymock runtime requires a valid quest id")

        if not _polymock_runtime_active:
            _polymock_saved_pause_on_combat = bool(tree.pause_on_combat)

        _polymock_runtime_active = True
        _polymock_forced_quest_id = requested_id
        _last_piece_signature = None
        _reset_round_manager()

        # Pin the state immediately; WidgetState.update() is re-pinned every tick too.
        widget_state.quest = _get_polymock_quest_by_id(requested_id)

        # Frenkey combat.py is the only skill controller inside Polymock.
        tree.pause_on_combat = False
        tree.SetHeadlessHeroAIEnabled(False, reset_runtime=False)
        return

    _polymock_runtime_active = False
    _polymock_forced_quest_id = None
    _last_piece_signature = None
    _reset_round_manager()
    widget_state.quest = None

    tree.SetHeadlessHeroAIEnabled(True, reset_runtime=False)
    if _polymock_saved_pause_on_combat is not None:
        tree.pause_on_combat = bool(_polymock_saved_pause_on_combat)
    _polymock_saved_pause_on_combat = None


def _polymock_prepare_tree(quest_id: int, label: str) -> BehaviorTree:
    return _immediate_action(
        f"{label} - Prepare Polymock Runtime",
        lambda: _set_polymock_runtime(int(quest_id), True),
    )


def _polymock_restore_tree(label: str) -> BehaviorTree:
    return _immediate_action(
        f"{label} - Restore HeroAI",
        lambda: _set_polymock_runtime(None, False),
    )


def _restore_polymock_runtime_if_idle(tree: BottingTree) -> None:
    """Safety net for Stop/failure while HeroAI is temporarily disabled."""
    if _polymock_runtime_active and not tree.IsStarted():
        _set_polymock_runtime(None, False)


def _try_clear_volumandus_diversion() -> bool:
    """
    Volumandus / Skeletal Mage:
    if Polymock Diversion is on the player, deliberately use Ether Signet
    (slot 7) to consume/remove it, as recommended by the walkthrough.
    """
    quest = getattr(widget_state, "quest", None)
    quest_id = int(getattr(quest, "quest_id", 0) or 0)
    if quest_id != VOLUMANDUS_QUEST_ID:
        return False

    try:
        diversion_id = int(GLOBAL_CACHE.Skill.GetID("Polymock_Diversion"))
    except Exception:
        diversion_id = 0

    if diversion_id <= 0:
        return False

    try:
        has_diversion = bool(
            GLOBAL_CACHE.Effects.HasEffect(
                int(Player.GetAgentID() or 0),
                diversion_id,
            )
        )
    except Exception:
        has_diversion = False

    if not has_diversion:
        return False

    try:
        ready = bool(combat_handler.IsSkillReady(7))
    except Exception:
        ready = False

    if not ready:
        return False

    _trace_log(
        MODULE_NAME,
        "[Volumandus] Diversion detected -> consuming it with Ether Signet (slot 7).",
    )
    try:
        return bool(combat_handler.UseSkill(7, int(Player.GetAgentID() or 0)))
    except Exception:
        return False


def _tick_polymock_combat() -> None:
    """
    Run the round manager and frenkey Polymock combat engine in parallel with
    the planner while it waits for the match to return to the outpost.
    """
    global _last_piece_signature, _last_combat_tick

    if not _polymock_runtime_active:
        return

    try:
        widget_state.update()
    except Exception as exc:
        _trace_log(
            MODULE_NAME,
            f"[DIAG] widget_state.update failed: {type(exc).__name__}: {exc}",
        )
        return

    _inject_forced_quest_if_needed()

    current_map_id = int(Map.GetMapID() or 0)
    if current_map_id not in POLYMOCK_ARENA_MAP_IDS:
        _last_piece_signature = None
        _reset_round_manager()
        return

    if POLYMOCK_VERBOSE_LOGS:
        _diagnostic_tick()

    now = time.monotonic()
    if now - _last_combat_tick < 0.20:
        return
    _last_combat_tick = now

    can_fight = _tick_polymock_round_manager()

    signature = _current_piece_signature()
    if (
        can_fight
        and _last_piece_signature is not None
        and signature != _last_piece_signature
        and any(signature)
    ):
        combat_handler.opener_used = False
        _trace_log(
            MODULE_NAME,
            f"New Polymock piece detected: {signature}; opener reset.",
        )

    _last_piece_signature = signature

    if not can_fight:
        return

    # Volumandus-specific anti-Diversion handling gets priority for this tick.
    if _try_clear_volumandus_diversion():
        return

    try:
        combat_handler.Fight()
    except Exception as exc:
        ConsoleLog(
            MODULE_NAME,
            f"Combat exception: {type(exc).__name__}: {exc}",
        )


# =============================================================================
# Small BT helpers
# =============================================================================

def _wait_for_any_map(
    map_ids: tuple[int, ...],
    *,
    timeout_ms: int,
    name: str,
) -> BehaviorTree:
    started_at: list[float | None] = [None]

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if started_at[0] is None:
            started_at[0] = time.monotonic()

        if int(Map.GetMapID() or 0) in map_ids:
            return BehaviorTree.NodeState.SUCCESS

        elapsed_ms = (time.monotonic() - float(started_at[0])) * 1000.0
        if elapsed_ms >= timeout_ms:
            ConsoleLog(
                MODULE_NAME,
                f"{name}: timeout waiting for maps {map_ids}; current={Map.GetMapID()}",
            )
            return BehaviorTree.NodeState.FAILURE

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=name,
            action_fn=_tick,
            aftercast_ms=0,
        )
    )


def _require_quest_completed(quest_id: int, label: str) -> BehaviorTree:
    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            quest = GLOBAL_CACHE.Quest.GetQuestData(quest_id)
            completed = bool(quest and quest.is_completed)
        except Exception:
            completed = False

        if completed:
            _trace_log(MODULE_NAME, f"{label}: quest completed.")
            return BehaviorTree.NodeState.SUCCESS

        ConsoleLog(
            MODULE_NAME,
            f"{label}: returned from Polymock but quest is NOT completed (match lost?).",
        )
        return BehaviorTree.NodeState.FAILURE

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"Check {label} Completed",
            action_fn=_check,
            aftercast_ms=0,
        )
    )


def _select_pieces(
    label: str,
    match_piece_dialogs: tuple[int, int, int],
    first_round_piece_dialog: int,
    selection_pos: Vec2f = POLYMOCK_SELECTION_POS,
    selector_name: str | None = None,
) -> BehaviorTree:
    """
    Polymock flow:
      1) xx85: choose the three pieces for the whole match.
      2) xx86: choose which of those pieces starts the current round.
      3) 0x87: start the first round.
      Later rounds are handled automatically by _tick_polymock_round_manager().

    Master Hoff can place Wokk at different coordinates depending on the
    generated arena instance. For Hoff, every selection action is therefore
    explicit: target Wokk -> interact -> MATCH 1 -> MATCH 2 -> MATCH 3 ->
    first ROUND piece -> retarget Wokk -> 0x87.
    """
    if selector_name:
        return BT.Sequence(
            name=f"{label} - Select Match Pieces + First Round Piece",
            children=[
                # Open Wokk's selector dialog without consuming MATCH #1.
                BT.TargetAgentByName(
                    agent_name=selector_name,
                    log=BT_FLOW_LOGS,
                ),
                BT.Wait(1_000),
                BT.InteractTarget(log=BT_FLOW_LOGS),
                BT.Wait(1_000),

                # Select the three Polymock pieces one by one.
                BT.SendDialog(match_piece_dialogs[0], log=BT_FLOW_LOGS),
                BT.Wait(500),
                BT.SendDialog(match_piece_dialogs[1], log=BT_FLOW_LOGS),
                BT.Wait(500),
                BT.SendDialog(match_piece_dialogs[2], log=BT_FLOW_LOGS),
                BT.Wait(500),

                # Choose the piece that will actually be used for round 1.
                BT.SendDialog(first_round_piece_dialog, log=BT_FLOW_LOGS),

                # Important: give the selected active Polymock time to load
                # BEFORE sending the final 0x87 start dialog.
                BT.Wait(500),

                # Hoff/Wokk quirk observed in live testing: retarget Wokk before
                # sending the final 0x87 launch dialog.
                BT.TargetAgentByName(
                    agent_name=selector_name,
                    log=BT_FLOW_LOGS,
                ),
                BT.Wait(1_000),
                BT.SendDialog(START_MATCH_DIALOG, log=BT_FLOW_LOGS),
                BT.Wait(1_600),
            ],
        )

    # All other Polymock opponents keep the already validated coordinate flow.
    return BT.Sequence(
        name=f"{label} - Select Match Pieces + First Round Piece",
        children=[
            BT.MoveAndDialog(
                selection_pos,
                match_piece_dialogs[0],
                log=BT_FLOW_LOGS,
            ),
            BT.Wait(600),
            BT.SendDialog(match_piece_dialogs[1], log=BT_FLOW_LOGS),
            BT.Wait(600),
            BT.SendDialog(match_piece_dialogs[2], log=BT_FLOW_LOGS),
            BT.Wait(5_000),

            BT.SendDialog(first_round_piece_dialog, log=BT_FLOW_LOGS),
            BT.Wait(1_000),

            BT.SendDialog(START_MATCH_DIALOG, log=BT_FLOW_LOGS),
            BT.Wait(1_600),
        ],
    )


def _wait_for_arena(label: str) -> BehaviorTree:
    return _wait_for_any_map(
        POLYMOCK_ARENA_MAP_IDS,
        timeout_ms=POLYMOCK_MAP_TIMEOUT_MS,
        name=f"{label} - Wait For Polymock Arena",
    )



def _quest_completed_condition(quest_id: int, label: str) -> BehaviorTree:
    """SUCCESS only when the given quest is currently completed."""
    def _check() -> bool:
        try:
            quest = GLOBAL_CACHE.Quest.GetQuestData(quest_id)
            completed = bool(quest and quest.is_completed)
        except Exception:
            completed = False

        if completed:
            _trace_log(MODULE_NAME, f"{label}: quest is completed.")
        return completed

    return BehaviorTree(
        BehaviorTree.ConditionNode(
            name=f"{label} - Quest Completed?",
            condition_fn=_check,
        )
    )


_blarp_attempt_counter = 0


def _blarp_attempt_log() -> BehaviorTree:
    def _log_attempt(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _blarp_attempt_counter
        _blarp_attempt_counter += 1
        _trace_log(
            MODULE_NAME,
            f"[BlarpRetry] Starting attempt #{_blarp_attempt_counter}.",
        )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Blarp - Log Attempt",
            action_fn=_log_attempt,
            aftercast_ms=0,
        )
    )


def _blarp_one_attempt_from_gadd() -> BehaviorTree:
    """
    Play exactly one complete Blarp match from Gadd's Encampment.

    SUCCESS  -> Blarp quest completed after returning to Gadd.
    FAILURE  -> match lost; surrounding repeater starts another attempt.
    """
    return BT.Sequence(
        name="Blarp - One Full Match Attempt",
        children=[
            _blarp_attempt_log(),
            _polymock_prepare_tree(BLARP_QUEST_ID, "Blarp"),

            # Re-enter the challenge from Gadd after either the first arrival
            # or a previous complete match loss.
            BT.MoveAndDialog(
                BLARP_POS,
                0x85,
                log=BT_FLOW_LOGS,
            ),
            _wait_for_arena("Blarp"),

            # Re-select the complete roster on EVERY retry.
            _select_pieces(
                "Blarp",
                (MATCH_KAPPA, MATCH_FIRE_IMP, MATCH_SKALE),
                ROUND_KAPPA,
            ),

            # combat.py + RoundManager run globally while this node waits. No timeout: wait until GW returns to the outpost.
            BT.WaitForMapLoad(
                map_name="Gadd's Encampment",
                timeout_ms=0,
            ),
            _polymock_restore_tree("Blarp"),
            BT.Wait(1_000),

            # Winning the complete match marks the quest complete.
            # A loss returns FAILURE here, causing a brand-new attempt.
            _require_quest_completed(
                BLARP_QUEST_ID,
                "Blarp",
            ),
        ],
    )


def _blarp_win_until_completed() -> BehaviorTree:
    """
    At Gadd's Encampment:
      already complete -> SUCCESS immediately
      not complete     -> play one match
          win  -> SUCCESS
          loss -> FAILURE -> repeat from Blarp NPC

    timeout_ms=0 intentionally means retry indefinitely until success.
    """
    check_or_attempt = BehaviorTree(
        BehaviorTree.SelectorNode(
            name="Blarp - Completed Or Fight Again",
            children=[
                _quest_completed_condition(
                    BLARP_QUEST_ID,
                    "Blarp",
                ).root,
                _blarp_one_attempt_from_gadd().root,
            ],
        )
    )

    return BehaviorTree(
        BehaviorTree.RepeaterUntilSuccessNode(
            name="Blarp - Retry Until Victory",
            child=check_or_attempt.root,
            timeout_ms=0,
        )
    )



_fonk_attempt_counter = 0


def _fonk_attempt_log() -> BehaviorTree:
    def _log_attempt(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _fonk_attempt_counter
        _fonk_attempt_counter += 1
        _trace_log(
            MODULE_NAME,
            f"[FonkRetry] Starting attempt #{_fonk_attempt_counter}.",
        )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Fonk - Log Attempt",
            action_fn=_log_attempt,
            aftercast_ms=0,
        )
    )


def _fonk_one_attempt_from_gunnar() -> BehaviorTree:
    """
    Play one full Fonk match from Gunnar's Hold.

    Roster from the repo counter_pieces:
      Gargoyle -> Kappa -> Fire Imp
    """
    return BT.Sequence(
        name="Fonk - One Full Match Attempt",
        children=[
            _fonk_attempt_log(),
            _polymock_prepare_tree(FONK_QUEST_ID, "Fonk"),

            BT.MoveAndDialog(
                FONK_POS,
                0x85,
                log=BT_FLOW_LOGS,
            ),
            _wait_for_arena("Fonk"),

            _select_pieces(
                "Fonk",
                (MATCH_GARGOYLE, MATCH_KAPPA, MATCH_FIRE_IMP),
                ROUND_GARGOYLE,
                selection_pos=FONK_SELECTION_POS,
            ),

            # No match timeout. Wait until GW returns us to Gunnar's Hold.
            BT.WaitForMapLoad(
                map_name="Gunnar's Hold",
                timeout_ms=0,
            ),
            _polymock_restore_tree("Fonk"),
            BT.Wait(1_000),

            _require_quest_completed(
                FONK_QUEST_ID,
                "Fonk",
            ),
        ],
    )


def _fonk_win_until_completed() -> BehaviorTree:
    check_or_attempt = BehaviorTree(
        BehaviorTree.SelectorNode(
            name="Fonk - Completed Or Fight Again",
            children=[
                _quest_completed_condition(
                    FONK_QUEST_ID,
                    "Fonk",
                ).root,
                _fonk_one_attempt_from_gunnar().root,
            ],
        )
    )

    return BehaviorTree(
        BehaviorTree.RepeaterUntilSuccessNode(
            name="Fonk - Retry Until Victory",
            child=check_or_attempt.root,
            timeout_ms=0,
        )
    )



_late_attempt_counters: dict[int, int] = {
    DUNE_TEARDRINKER_QUEST_ID: 0,
    GRULHAMMER_QUEST_ID: 0,
    VOLUMANDUS_QUEST_ID: 0,
}


def _late_attempt_log(quest_id: int) -> BehaviorTree:
    data = LAST_THREE_OPPONENT_DATA[int(quest_id)]
    label = str(data["label"])

    def _log_attempt(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        _late_attempt_counters[int(quest_id)] = (
            int(_late_attempt_counters.get(int(quest_id), 0)) + 1
        )
        _trace_log(
            MODULE_NAME,
            f"[{label}Retry] Starting attempt #{_late_attempt_counters[int(quest_id)]}.",
        )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"{label} - Log Attempt",
            action_fn=_log_attempt,
            aftercast_ms=0,
        )
    )


def _late_one_attempt(quest_id: int) -> BehaviorTree:
    """
    One complete Polymock attempt from the opponent's outpost.

    The NPC at opponent_pos gets 0x85 to enter the arena.
    The arena NPC at selector_pos receives xx85 x3, xx86, then 0x87.
    A loss returns to the outpost and produces FAILURE so the repeater retries.
    """
    data = LAST_THREE_OPPONENT_DATA[int(quest_id)]
    label = str(data["label"])
    outpost = str(data["outpost"])
    opponent_pos = data["opponent_pos"]
    selector_pos = data["selector_pos"]
    match_dialogs = data["match_dialogs"]
    first_round_dialog = int(data["first_round_dialog"])

    return BT.Sequence(
        name=f"{label} - One Full Match Attempt",
        children=[
            _late_attempt_log(int(quest_id)),
            _polymock_prepare_tree(int(quest_id), label),

            BT.MoveAndDialog(
                opponent_pos,
                0x85,
                log=BT_FLOW_LOGS,
            ),
            _wait_for_arena(label),

            _select_pieces(
                label,
                match_dialogs,
                first_round_dialog,
                selection_pos=selector_pos,
            ),

            # No overall match timeout.
            BT.WaitForMapLoad(
                map_name=outpost,
                timeout_ms=0,
            ),
            _polymock_restore_tree(label),
            BT.Wait(1_000),

            _require_quest_completed(
                int(quest_id),
                label,
            ),
        ],
    )


def _late_win_until_completed(quest_id: int) -> BehaviorTree:
    data = LAST_THREE_OPPONENT_DATA[int(quest_id)]
    label = str(data["label"])

    check_or_attempt = BehaviorTree(
        BehaviorTree.SelectorNode(
            name=f"{label} - Completed Or Fight Again",
            children=[
                _quest_completed_condition(
                    int(quest_id),
                    label,
                ).root,
                _late_one_attempt(int(quest_id)).root,
            ],
        )
    )

    return BehaviorTree(
        BehaviorTree.RepeaterUntilSuccessNode(
            name=f"{label} - Retry Until Victory",
            child=check_or_attempt.root,
            timeout_ms=0,
        )
    )


def _steps_late_opponent(quest_id: int) -> list[PlannerStep]:
    data = LAST_THREE_OPPONENT_DATA[int(quest_id)]
    label = str(data["label"])
    outpost = str(data["outpost"])
    accept_dialog = int(data["accept_dialog"])
    reward_dialog = int(data["reward_dialog"])

    return [
        (
            f"{label} - 001 Travel Rata Sum",
            lambda: BT.Travel(target_map_name="Rata Sum", log=BT_FLOW_LOGS),
        ),
        (
            f"{label} - 002 Accept Quest",
            lambda: BT.MoveAndDialog(
                POLYMOCK_HOFF_POS,
                accept_dialog,
                log=BT_FLOW_LOGS,
            ),
        ),

        (
            f"{label} - 003 Travel {outpost}",
            lambda: BT.Travel(target_map_name=outpost, log=BT_FLOW_LOGS),
        ),
        (
            f"{label} - 004 Retry Until Victory",
            lambda: _late_win_until_completed(int(quest_id)),
        ),

        (
            f"{label} - 005 Travel Rata Sum",
            lambda: BT.Travel(target_map_name="Rata Sum", log=BT_FLOW_LOGS),
        ),
        (
            f"{label} - 006 Settle",
            lambda: BT.Wait(POST_LOAD_WAIT_MS),
        ),
        (
            f"{label} - 007 Claim Reward",
            lambda: BT.MoveAndDialog(
                POLYMOCK_HOFF_POS,
                reward_dialog,
                log=BT_FLOW_LOGS,
            ),
        ),
        (f"{label} - 008 Close Reward Window",
         lambda: BT.CancelSkillRewardWindow())
    ]


def _steps_dune() -> list[PlannerStep]:
    steps = _steps_late_opponent(DUNE_TEARDRINKER_QUEST_ID)
    steps.append(
        (
            "Dune Teardrinker - 009 Register Aloe Seed Reward",
            lambda: BT.MoveAndDialog(
                POLYMOCK_REGISTER_POS,
                REGISTER_ALOE_SEED,
                log=BT_FLOW_LOGS,
            ),
        )
    )
    return steps


def _steps_grulhammer() -> list[PlannerStep]:
    steps = _steps_late_opponent(GRULHAMMER_QUEST_ID)
    steps.append(
        (
            "Grulhammer - 009 Register Fire Elemental Reward",
            lambda: BT.MoveAndDialog(
                POLYMOCK_REGISTER_POS,
                REGISTER_FIRE_ELEMENTAL,
                log=BT_FLOW_LOGS,
            ),
        )
    )
    return steps


def _steps_volumandus() -> list[PlannerStep]:
    steps = _steps_late_opponent(VOLUMANDUS_QUEST_ID)
    steps.append(
        (
            "Volumandus - 009 Register Ice Elemental Reward",
            lambda: BT.MoveAndDialog(
                POLYMOCK_REGISTER_POS,
                REGISTER_ICE_ELEMENTAL,
                log=BT_FLOW_LOGS,
            ),
        )
    )
    return steps



_hoff_attempt_counter = 0


def _hoff_attempt_log() -> BehaviorTree:
    def _log_attempt(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _hoff_attempt_counter
        _hoff_attempt_counter += 1
        _trace_log(
            MODULE_NAME,
            f"[HoffRetry] Starting attempt #{_hoff_attempt_counter}.",
        )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Master Hoff - Log Attempt",
            action_fn=_log_attempt,
            aftercast_ms=0,
        )
    )


def _hoff_one_attempt_from_rata() -> BehaviorTree:
    """
    One complete Master Hoff match from Rata Sum.

    Hoff dialog 0x84 teleports into a Polymock instance.
    The generated arena layout can vary, so the selector NPC is resolved
    by name ("Wokk") instead of by a fixed coordinate.
    """
    return BT.Sequence(
        name="Master Hoff - One Full Match Attempt",
        children=[
            _hoff_attempt_log(),
            _polymock_prepare_tree(HOFF_QUEST_ID, "Master Hoff"),

            BT.MoveAndDialog(
                POLYMOCK_HOFF_POS,
                HOFF_START_DIALOG,
                log=BT_FLOW_LOGS,
            ),
            _wait_for_arena("Master Hoff"),

            _select_pieces(
                "Master Hoff",
                (
                    MATCH_ICE_ELEMENTAL,
                    MATCH_EARTH_ELEMENTAL,
                    MATCH_FIRE_ELEMENTAL,
                ),
                ROUND_ICE_ELEMENTAL,
                selector_name=HOFF_SELECTOR_NAME,
            ),

            # No match timeout; GW returns us to Rata Sum.
            BT.WaitForMapLoad(
                map_name="Rata Sum",
                timeout_ms=0,
            ),
            _polymock_restore_tree("Master Hoff"),
            BT.Wait(1_000),

            _require_quest_completed(
                HOFF_QUEST_ID,
                "Master Hoff",
            ),
        ],
    )


def _hoff_win_until_completed() -> BehaviorTree:
    check_or_attempt = BehaviorTree(
        BehaviorTree.SelectorNode(
            name="Master Hoff - Completed Or Fight Again",
            children=[
                _quest_completed_condition(
                    HOFF_QUEST_ID,
                    "Master Hoff",
                ).root,
                _hoff_one_attempt_from_rata().root,
            ],
        )
    )

    return BehaviorTree(
        BehaviorTree.RepeaterUntilSuccessNode(
            name="Master Hoff - Retry Until Victory",
            child=check_or_attempt.root,
            timeout_ms=0,
        )
    )


def _steps_hoff() -> list[PlannerStep]:
    return [
        (
            "Master Hoff - 001 Travel Rata Sum",
            lambda: BT.Travel(
                target_map_name="Rata Sum",
                log=BT_FLOW_LOGS,
            ),
        ),
        (
            "Master Hoff - 002 Accept Final Quest",
            lambda: BT.MoveAndDialog(
                POLYMOCK_HOFF_POS,
                HOFF_ACCEPT_DIALOG,
                log=BT_FLOW_LOGS,
            ),
        ),
        (
            "Master Hoff - 003 Retry Until Victory",
            lambda: _hoff_win_until_completed(),
        ),
        (
            "Master Hoff - 004 Settle",
            lambda: BT.Wait(POST_LOAD_WAIT_MS),
        ),
        (
            "Master Hoff - 005 Claim Final Reward",
            lambda: BT.MoveAndDialog(
                POLYMOCK_HOFF_POS,
                HOFF_REWARD_DIALOG,
                log=BT_FLOW_LOGS,
            ),
        ),
    ]


# =============================================================================
# Quest / combat sequences
# =============================================================================

def _steps_yulma(*, include_reward: bool = True) -> list[PlannerStep]:
    steps: list[PlannerStep] = [
        ("Yulma - 001 Travel Rata Sum", lambda: BT.Travel(target_map_name="Rata Sum", log=BT_FLOW_LOGS)),
        ("Yulma - 002 Accept Quest", lambda: BT.MoveAndDialog(POLYMOCK_HOFF_POS, YULMA_ACCEPT_DIALOG, log=BT_FLOW_LOGS)),

        # Initial starter pieces registration.
        ("Yulma - 003 Register Starter Piece 1", lambda: BT.MoveAndDialog(POLYMOCK_REGISTER_POS, REGISTER_STARTER_1, log=BT_FLOW_LOGS)),
        ("Yulma - 004 Register Starter Piece 2", lambda: BT.SendDialog(REGISTER_STARTER_2, log=BT_FLOW_LOGS)),
        ("Yulma - 005 Register Starter Piece 3", lambda: BT.SendDialog(REGISTER_STARTER_3, log=BT_FLOW_LOGS)),

        ("Yulma - 006 Prepare Polymock", lambda: _polymock_prepare_tree(YULMA_QUEST_ID, "Yulma")),
        ("Yulma - 007 Start Challenge", lambda: BT.MoveAndDialog(YULMA_POS, 0x85, log=BT_FLOW_LOGS)),
        ("Yulma - 008 Wait Arena", lambda: _wait_for_arena("Yulma")),
        (
            "Yulma - 009 Select Pieces And Start",
            lambda: _select_pieces(
                "Yulma",
                (MATCH_GARGOYLE, MATCH_MERGOYLE, MATCH_SKALE),
                ROUND_GARGOYLE,
            ),
        ),

        # The combat handler is ticked globally while this planner waits.
        ("Yulma - 010 Wait Return Rata Sum", lambda: BT.WaitForMapLoad(map_name="Rata Sum", timeout_ms=0)),
        ("Yulma - 011 Restore HeroAI", lambda: _polymock_restore_tree("Yulma")),
        ("Yulma - 012 Settle", lambda: BT.Wait(POST_LOAD_WAIT_MS)),
        ("Yulma - 013 Verify Win", lambda: _require_quest_completed(YULMA_QUEST_ID, "Yulma")),
    ]

    if include_reward:
        steps.extend(
            [
                (
                    "Yulma - 014 Reward",
                    lambda: BT.MoveAndDialog(
                        POLYMOCK_HOFF_POS,
                        YULMA_REWARD_DIALOG,
                        log=BT_FLOW_LOGS,
                    ),
                ),
                (
                    "Yulma - 015 Register Fire Imp Reward",
                    lambda: BT.MoveAndDialog(
                        POLYMOCK_REGISTER_POS,
                        REGISTER_FIRE_IMP,
                        log=BT_FLOW_LOGS,
                    ),
                ),
            ]
        )
    return steps


def _steps_plurgg(*, include_reward: bool = True) -> list[PlannerStep]:
    steps: list[PlannerStep] = [
        ("Plurgg - 001 Travel Rata Sum", lambda: BT.Travel(target_map_name="Rata Sum", log=BT_FLOW_LOGS)),
        ("Plurgg - 002 Accept Quest", lambda: BT.MoveAndDialog(POLYMOCK_HOFF_POS, PLURGG_ACCEPT_DIALOG, log=BT_FLOW_LOGS)),

        ("Plurgg - 003 Travel Vlox's Falls", lambda: BT.Travel(target_map_name="Vlox's Falls", log=BT_FLOW_LOGS)),
        ("Plurgg - 004 Prepare Polymock", lambda: _polymock_prepare_tree(PLURGG_QUEST_ID, "Plurgg")),
        ("Plurgg - 005 Start Challenge", lambda: BT.MoveAndDialog(PLURGG_POS, 0x85, log=BT_FLOW_LOGS)),
        ("Plurgg - 006 Wait Arena", lambda: _wait_for_arena("Plurgg")),
        (
            "Plurgg - 007 Select Pieces And Start",
            lambda: _select_pieces(
                "Plurgg",
                (MATCH_SKALE, MATCH_FIRE_IMP, MATCH_GARGOYLE),
                ROUND_SKALE,
            ),
        ),

        ("Plurgg - 008 Wait Return Vlox", lambda: BT.WaitForMapLoad(map_name="Vlox's Falls", timeout_ms=0)),
        ("Plurgg - 009 Restore HeroAI", lambda: _polymock_restore_tree("Plurgg")),
        ("Plurgg - 010 Travel Rata Sum", lambda: BT.Travel(target_map_name="Rata Sum", log=BT_FLOW_LOGS)),
        ("Plurgg - 011 Settle", lambda: BT.Wait(POST_LOAD_WAIT_MS)),
        ("Plurgg - 012 Verify Win", lambda: _require_quest_completed(PLURGG_QUEST_ID, "Plurgg")),
    ]

    if include_reward:
        steps.extend(
            [
                (
                    "Plurgg - 013 Reward",
                    lambda: BT.MoveAndDialog(
                        POLYMOCK_HOFF_POS,
                        PLURGG_REWARD_DIALOG,
                        log=BT_FLOW_LOGS,
                    ),
                ),
                (
                    "Plurgg - 014 Register Kappa Reward",
                    lambda: BT.MoveAndDialog(
                        POLYMOCK_REGISTER_POS,
                        REGISTER_KAPPA,
                        log=BT_FLOW_LOGS,
                    ),
                ),
            ]
        )
    return steps


def _steps_blarp() -> list[PlannerStep]:
    return [
        ("Blarp - 001 Travel Rata Sum", lambda: BT.Travel(target_map_name="Rata Sum", log=BT_FLOW_LOGS)),
        ("Blarp - 002 Accept Quest", lambda: BT.MoveAndDialog(POLYMOCK_HOFF_POS, BLARP_ACCEPT_DIALOG, log=BT_FLOW_LOGS)),
        ("Blarp - 003 Travel Gadd's Encampment", lambda: BT.Travel(target_map_name="Gadd's Encampment", log=BT_FLOW_LOGS)),

        # This single step loops complete Polymock matches at Gadd.
        # Loss:
        #   Gadd -> Blarp -> arena -> roster -> rounds -> Gadd -> retry
        # Win:
        #   Gadd -> quest completed -> SUCCESS -> travel Rata Sum
        ("Blarp - 004 Retry Until Victory", lambda: _blarp_win_until_completed()),

        ("Blarp - 005 Travel Rata Sum", lambda: BT.Travel(target_map_name="Rata Sum", log=BT_FLOW_LOGS)),
        ("Blarp - 006 Settle", lambda: BT.Wait(POST_LOAD_WAIT_MS)),
        (
            "Blarp - 007 Claim Reward",
            lambda: BT.MoveAndDialog(
                POLYMOCK_HOFF_POS,
                BLARP_REWARD_DIALOG,
                log=BT_FLOW_LOGS,
            ),
        ),
        (
            "Blarp - 008 Register Ice Imp Reward",
            lambda: BT.MoveAndDialog(
                POLYMOCK_REGISTER_POS,
                REGISTER_ICE_IMP,
                log=BT_FLOW_LOGS,
            ),
        ),
    ]



def _steps_fonk() -> list[PlannerStep]:
    return [
        ("Fonk - 001 Travel Rata Sum", lambda: BT.Travel(target_map_name="Rata Sum", log=BT_FLOW_LOGS)),
        (
            "Fonk - 002 Accept Quest",
            lambda: BT.MoveAndDialog(
                POLYMOCK_HOFF_POS,
                FONK_ACCEPT_DIALOG,
                log=BT_FLOW_LOGS,
            ),
        ),
        ("Fonk - 003 Travel Gunnar's Hold", lambda: BT.Travel(target_map_name="Gunnar's Hold", log=BT_FLOW_LOGS)),

        # Loss -> automatic return Gunnar -> challenge restarts.
        # Win  -> quest complete -> leave retry loop.
        ("Fonk - 004 Retry Until Victory", lambda: _fonk_win_until_completed()),

        ("Fonk - 005 Travel Rata Sum", lambda: BT.Travel(target_map_name="Rata Sum", log=BT_FLOW_LOGS)),
        ("Fonk - 006 Settle", lambda: BT.Wait(POST_LOAD_WAIT_MS)),
        (
            "Fonk - 007 Claim Reward",
            lambda: BT.MoveAndDialog(
                POLYMOCK_HOFF_POS,
                FONK_REWARD_DIALOG,
                log=BT_FLOW_LOGS,
            ),
        ),
        (
            "Fonk - 008 Register Earth Elemental Reward",
            lambda: BT.MoveAndDialog(
                POLYMOCK_REGISTER_POS,
                REGISTER_EARTH_ELEMENTAL,
                log=BT_FLOW_LOGS,
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Runtime Polymock progression resolver
# ---------------------------------------------------------------------------

POLYMOCK_CHAIN_QUEST_IDS: tuple[int, ...] = (
    YULMA_QUEST_ID,
    PLURGG_QUEST_ID,
    BLARP_QUEST_ID,
    FONK_QUEST_ID,
    DUNE_TEARDRINKER_QUEST_ID,
    GRULHAMMER_QUEST_ID,
    VOLUMANDUS_QUEST_ID,
    HOFF_QUEST_ID,
)

POLYMOCK_CHAIN_LABELS: dict[int, str] = {
    YULMA_QUEST_ID: "Yulma",
    PLURGG_QUEST_ID: "Plurgg",
    BLARP_QUEST_ID: "Blarp",
    FONK_QUEST_ID: "Fonk",
    DUNE_TEARDRINKER_QUEST_ID: "Dune Teardrinker",
    GRULHAMMER_QUEST_ID: "Grulhammer Silverfist",
    VOLUMANDUS_QUEST_ID: "Necromancer Volumandus",
    HOFF_QUEST_ID: "Master Hoff",
}

POLYMOCK_ACCEPT_DIALOG_TO_QUEST_ID: dict[int, int] = {
    YULMA_ACCEPT_DIALOG: YULMA_QUEST_ID,
    PLURGG_ACCEPT_DIALOG: PLURGG_QUEST_ID,
    BLARP_ACCEPT_DIALOG: BLARP_QUEST_ID,
    FONK_ACCEPT_DIALOG: FONK_QUEST_ID,
    DUNE_TEARDRINKER_ACCEPT_DIALOG: DUNE_TEARDRINKER_QUEST_ID,
    GRULHAMMER_ACCEPT_DIALOG: GRULHAMMER_QUEST_ID,
    VOLUMANDUS_ACCEPT_DIALOG: VOLUMANDUS_QUEST_ID,
    HOFF_ACCEPT_DIALOG: HOFF_QUEST_ID,
}


def _polymock_chain_index(quest_id: int) -> int:
    try:
        return POLYMOCK_CHAIN_QUEST_IDS.index(int(quest_id))
    except ValueError:
        return -1


def _polymock_full_steps_for_quest(quest_id: int) -> list[PlannerStep]:
    quest_id = int(quest_id)
    if quest_id == YULMA_QUEST_ID:
        return _steps_yulma(include_reward=True)
    if quest_id == PLURGG_QUEST_ID:
        return _steps_plurgg(include_reward=True)
    if quest_id == BLARP_QUEST_ID:
        return _steps_blarp()
    if quest_id == FONK_QUEST_ID:
        return _steps_fonk()
    if quest_id == DUNE_TEARDRINKER_QUEST_ID:
        return _steps_dune()
    if quest_id == GRULHAMMER_QUEST_ID:
        return _steps_grulhammer()
    if quest_id == VOLUMANDUS_QUEST_ID:
        return _steps_volumandus()
    if quest_id == HOFF_QUEST_ID:
        return _steps_hoff()
    return []


def _polymock_reward_only_steps(quest_id: int) -> list[PlannerStep]:
    """Finish a Polymock quest that is already complete but not yet rewarded."""
    quest_id = int(quest_id)

    if quest_id == YULMA_QUEST_ID:
        return [
            ("Yulma Resume - Settle", lambda: BT.Wait(POST_LOAD_WAIT_MS)),
            (
                "Yulma Resume - Claim Reward",
                lambda: BT.MoveAndDialog(
                    POLYMOCK_HOFF_POS,
                    YULMA_REWARD_DIALOG,
                    log=BT_FLOW_LOGS,
                ),
            ),
            (
                "Yulma Resume - Register Fire Imp Reward",
                lambda: BT.MoveAndDialog(
                    POLYMOCK_REGISTER_POS,
                    REGISTER_FIRE_IMP,
                    log=BT_FLOW_LOGS,
                ),
            ),
        ]

    if quest_id == PLURGG_QUEST_ID:
        return [
            ("Plurgg Resume - Settle", lambda: BT.Wait(POST_LOAD_WAIT_MS)),
            (
                "Plurgg Resume - Claim Reward",
                lambda: BT.MoveAndDialog(
                    POLYMOCK_HOFF_POS,
                    PLURGG_REWARD_DIALOG,
                    log=BT_FLOW_LOGS,
                ),
            ),
            (
                "Plurgg Resume - Register Kappa Reward",
                lambda: BT.MoveAndDialog(
                    POLYMOCK_REGISTER_POS,
                    REGISTER_KAPPA,
                    log=BT_FLOW_LOGS,
                ),
            ),
        ]

    if quest_id == BLARP_QUEST_ID:
        return [
            ("Blarp Resume - Settle", lambda: BT.Wait(POST_LOAD_WAIT_MS)),
            (
                "Blarp Resume - Claim Reward",
                lambda: BT.MoveAndDialog(
                    POLYMOCK_HOFF_POS,
                    BLARP_REWARD_DIALOG,
                    log=BT_FLOW_LOGS,
                ),
            ),
            (
                "Blarp Resume - Register Ice Imp Reward",
                lambda: BT.MoveAndDialog(
                    POLYMOCK_REGISTER_POS,
                    REGISTER_ICE_IMP,
                    log=BT_FLOW_LOGS,
                ),
            ),
        ]

    if quest_id == FONK_QUEST_ID:
        return [
            ("Fonk Resume - Settle", lambda: BT.Wait(POST_LOAD_WAIT_MS)),
            (
                "Fonk Resume - Claim Reward",
                lambda: BT.MoveAndDialog(
                    POLYMOCK_HOFF_POS,
                    FONK_REWARD_DIALOG,
                    log=BT_FLOW_LOGS,
                ),
            ),
            (
                "Fonk Resume - Register Earth Elemental Reward",
                lambda: BT.MoveAndDialog(
                    POLYMOCK_REGISTER_POS,
                    REGISTER_EARTH_ELEMENTAL,
                    log=BT_FLOW_LOGS,
                ),
            ),
        ]

    if quest_id == DUNE_TEARDRINKER_QUEST_ID:
        return [
            ("Dune Resume - Settle", lambda: BT.Wait(POST_LOAD_WAIT_MS)),
            (
                "Dune Resume - Claim Reward",
                lambda: BT.MoveAndDialog(
                    POLYMOCK_HOFF_POS,
                    DUNE_TEARDRINKER_REWARD_DIALOG,
                    log=BT_FLOW_LOGS,
                ),
            ),
            ("Dune Resume - Close Reward Window", lambda: BT.CancelSkillRewardWindow()),
            (
                "Dune Resume - Register Aloe Seed Reward",
                lambda: BT.MoveAndDialog(
                    POLYMOCK_REGISTER_POS,
                    REGISTER_ALOE_SEED,
                    log=BT_FLOW_LOGS,
                ),
            ),
        ]

    if quest_id == GRULHAMMER_QUEST_ID:
        return [
            ("Grulhammer Resume - Settle", lambda: BT.Wait(POST_LOAD_WAIT_MS)),
            (
                "Grulhammer Resume - Claim Reward",
                lambda: BT.MoveAndDialog(
                    POLYMOCK_HOFF_POS,
                    GRULHAMMER_REWARD_DIALOG,
                    log=BT_FLOW_LOGS,
                ),
            ),
            ("Grulhammer Resume - Close Reward Window", lambda: BT.CancelSkillRewardWindow()),
            (
                "Grulhammer Resume - Register Fire Elemental Reward",
                lambda: BT.MoveAndDialog(
                    POLYMOCK_REGISTER_POS,
                    REGISTER_FIRE_ELEMENTAL,
                    log=BT_FLOW_LOGS,
                ),
            ),
        ]

    if quest_id == VOLUMANDUS_QUEST_ID:
        return [
            ("Volumandus Resume - Settle", lambda: BT.Wait(POST_LOAD_WAIT_MS)),
            (
                "Volumandus Resume - Claim Reward",
                lambda: BT.MoveAndDialog(
                    POLYMOCK_HOFF_POS,
                    VOLUMANDUS_REWARD_DIALOG,
                    log=BT_FLOW_LOGS,
                ),
            ),
            ("Volumandus Resume - Close Reward Window", lambda: BT.CancelSkillRewardWindow()),
            (
                "Volumandus Resume - Register Ice Elemental Reward",
                lambda: BT.MoveAndDialog(
                    POLYMOCK_REGISTER_POS,
                    REGISTER_ICE_ELEMENTAL,
                    log=BT_FLOW_LOGS,
                ),
            ),
        ]

    if quest_id == HOFF_QUEST_ID:
        return [
            ("Master Hoff Resume - Settle", lambda: BT.Wait(POST_LOAD_WAIT_MS)),
            (
                "Master Hoff Resume - Claim Final Reward",
                lambda: BT.MoveAndDialog(
                    POLYMOCK_HOFF_POS,
                    HOFF_REWARD_DIALOG,
                    log=BT_FLOW_LOGS,
                ),
            ),
        ]

    return []


def _planner_steps_to_tree(name: str, steps: list[PlannerStep]) -> BehaviorTree:
    children: list[BehaviorTree] = []
    for _step_name, factory in steps:
        children.append(factory())
    if not children:
        return BT.Succeeder(name=f"{name} - Nothing To Do")
    return BT.Sequence(name=name, children=children)


def _polymock_build_chain_from(
    start_quest_id: int,
    target_quest_id: int,
    *,
    start_is_complete: bool,
) -> BehaviorTree:
    start_index = _polymock_chain_index(start_quest_id)
    target_index = _polymock_chain_index(target_quest_id)

    if start_index < 0 or target_index < 0:
        return BT.Failer(name="Polymock Resolver - Invalid Quest Id")

    if start_index > target_index:
        return BT.Sequence(
            name="Polymock Resolver - Progress Already Past Target",
            children=[
                BT.LogMessage(
                    message=(
                        f"Polymock progression is already past "
                        f"{POLYMOCK_CHAIN_LABELS[target_quest_id]}; nothing to run."
                    ),
                    module_name=MODULE_NAME,
                ),
                BT.Succeeder("Polymock Target Already Passed"),
            ],
        )

    steps: list[PlannerStep] = []
    if start_is_complete:
        steps.extend(_polymock_reward_only_steps(start_quest_id))
    else:
        # Re-sending an already-active quest's accept dialog is harmless: the
        # low-level SendDialog returns immediately even when the option is no
        # longer visible. This lets the same validated quest flow handle both
        # newly offered and already-active quests. Yulma also re-sends the
        # starter-piece registration dialogs, which is safe and covers the
        # edge case where the quest was accepted but setup was interrupted.
        steps.extend(_polymock_full_steps_for_quest(start_quest_id))

    for quest_id in POLYMOCK_CHAIN_QUEST_IDS[start_index + 1 : target_index + 1]:
        steps.extend(_polymock_full_steps_for_quest(quest_id))

    label = POLYMOCK_CHAIN_LABELS[start_quest_id]
    target_label = POLYMOCK_CHAIN_LABELS[target_quest_id]
    return _planner_steps_to_tree(
        f"Polymock Resume {label} -> {target_label}",
        steps,
    )


def _polymock_quest_log_state() -> tuple[int | None, bool]:
    """Return (quest_id, is_complete) for the earliest Polymock quest in the log."""
    try:
        raw_ids = GLOBAL_CACHE.Quest.GetQuestLogIds() or []
        log_ids = {int(value) for value in raw_ids}
    except Exception:
        log_ids = set()

    for quest_id in POLYMOCK_CHAIN_QUEST_IDS:
        if quest_id not in log_ids:
            continue

        try:
            completed = bool(GLOBAL_CACHE.Quest.IsQuestCompleted(quest_id))
        except Exception:
            try:
                quest = GLOBAL_CACHE.Quest.GetQuestData(quest_id)
                completed = bool(quest and quest.is_completed)
            except Exception:
                completed = False

        return int(quest_id), bool(completed)

    return None, False


def _wait_for_hoff_polymock_offer(resolved: dict[str, int | None]) -> BehaviorTree:
    state_data = {"started": 0.0, "last_seen": ()}

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        now = time.monotonic()
        if state_data["started"] <= 0.0:
            state_data["started"] = now

        try:
            buttons = Dialog.get_active_dialog_buttons() or []
        except Exception:
            buttons = []

        visible_ids = tuple(
            int(getattr(button, "dialog_id", 0) or 0)
            for button in buttons
            if int(getattr(button, "dialog_id", 0) or 0) > 0
        )
        state_data["last_seen"] = visible_ids

        offered = [
            POLYMOCK_ACCEPT_DIALOG_TO_QUEST_ID[dialog_id]
            for dialog_id in visible_ids
            if dialog_id in POLYMOCK_ACCEPT_DIALOG_TO_QUEST_ID
        ]
        if offered:
            offered.sort(key=_polymock_chain_index)
            quest_id = int(offered[0])
            resolved["quest_id"] = quest_id
            ConsoleLog(
                MODULE_NAME,
                (
                    "Polymock resolver: Hoff currently offers "
                    f"{POLYMOCK_CHAIN_LABELS[quest_id]} "
                    f"(quest {quest_id})."
                ),
            )
            return BehaviorTree.NodeState.SUCCESS

        if now - float(state_data["started"]) >= 6.0:
            ConsoleLog(
                MODULE_NAME,
                (
                    "Polymock resolver: no known Polymock quest offer found at Hoff. "
                    f"Visible dialog ids={visible_ids}."
                ),
                PySystem.Console.MessageType.Error,
            )
            return BehaviorTree.NodeState.FAILURE

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Polymock Resolver - Wait For Hoff Offer",
            action_fn=_tick,
            aftercast_ms=0,
        )
    )


def _polymock_resolve_from_hoff_dialog(target_quest_id: int) -> BehaviorTree:
    resolved: dict[str, int | None] = {"quest_id": None}

    def _build_resolved_chain(_node: BehaviorTree.Node) -> BehaviorTree:
        quest_id = resolved.get("quest_id")
        if quest_id is None:
            return BT.Failer(name="Polymock Resolver - Hoff Offer Missing")
        return _polymock_build_chain_from(
            int(quest_id),
            int(target_quest_id),
            start_is_complete=False,
        )

    return BT.Sequence(
        name="Polymock Resolver - Read Hoff Progress",
        children=[
            BT.MoveAndInteract(
                POLYMOCK_HOFF_POS,
                log=BT_FLOW_LOGS,
            ),
            BT.Wait(500),
            _wait_for_hoff_polymock_offer(resolved),
            BT.Subtree(
                name="Polymock Resolver - Build Offered Chain",
                subtree_fn=_build_resolved_chain,
            ),
        ],
    )


def _polymock_resume_to_target(target_quest_id: int) -> BehaviorTree:
    target_quest_id = int(target_quest_id)

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        quest_id, completed = _polymock_quest_log_state()

        if quest_id is not None:
            ConsoleLog(
                MODULE_NAME,
                (
                    "Polymock resolver: quest log resume point = "
                    f"{POLYMOCK_CHAIN_LABELS[quest_id]} "
                    f"({'complete/reward pending' if completed else 'active'})."
                ),
            )
            return _polymock_build_chain_from(
                quest_id,
                target_quest_id,
                start_is_complete=completed,
            )

        ConsoleLog(
            MODULE_NAME,
            "Polymock resolver: no Polymock quest in journal; checking Hoff's current offer.",
        )
        return _polymock_resolve_from_hoff_dialog(target_quest_id)

    return BT.Subtree(
        name=f"Resolve Polymock Progress To {POLYMOCK_CHAIN_LABELS[target_quest_id]}",
        subtree_fn=_build,
    )


def _steps_polymock_resume_target(target_quest_id: int) -> list[PlannerStep]:
    target_label = POLYMOCK_CHAIN_LABELS[int(target_quest_id)]
    return [
        (
            f"Polymock Resume - 001 Travel Rata Sum for {target_label}",
            lambda: BT.Travel(target_map_name="Rata Sum", log=BT_FLOW_LOGS),
        ),
        (
            f"Polymock Resume - 002 Resolve Progression to {target_label}",
            lambda: _polymock_resume_to_target(int(target_quest_id)),
        ),
    ]


# ---------------------------------------------------------------------------
# Asura summon skills unlocked through the validated Polymock progression
# ---------------------------------------------------------------------------

def _steps_unlock_summon_naga_shaman() -> list[PlannerStep]:
    """Resume current Polymock progress and continue through Dune Teardrinker."""
    return _steps_polymock_resume_target(DUNE_TEARDRINKER_QUEST_ID)


def _steps_unlock_summon_ruby_djinn() -> list[PlannerStep]:
    """Resume current Polymock progress and continue through Grulhammer Silverfist."""
    return _steps_polymock_resume_target(GRULHAMMER_QUEST_ID)


def _steps_unlock_summon_ice_imp() -> list[PlannerStep]:
    """Resume current Polymock progress and continue through Necromancer Volumandus."""
    return _steps_polymock_resume_target(VOLUMANDUS_QUEST_ID)


def _steps_unlock_summon_mursaat() -> list[PlannerStep]:
    """Resume current Polymock progress and continue through Master Hoff."""
    return _steps_polymock_resume_target(HOFF_QUEST_ID)

# ---------------------------------------------------------------------------
# Converted legacy routes
# ---------------------------------------------------------------------------

def _steps_unlock_air_of_superiority() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Air of Superiority - 001 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Air of Superiority - 002 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837d01, log=True)))
    steps.append(('Air of Superiority - 003 Travel', lambda: BT.Travel(target_map_name='Olafstead', log=True)))
    steps.append(('Air of Superiority - 004 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-1503, 1201.0), target_map_name='Varajar Fells', timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.extend(_movement_point_steps('Air of Superiority - 005 Route', AIR_OF_SUPERIORITY_PATH_01))
    steps.append(('Air of Superiority - 006 Wait For Clear Enemies In Area', lambda: BT.WaitForClearEnemiesInArea(*AIR_OF_SUPERIORITY_PATH_01[-1], stable_clear_ms=60000)))
    steps.append(('Air of Superiority - 007 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(22648.0, 1078.0), 0x837d07, log=True)))
    steps.append(('Air of Superiority - 008 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    steps.append(('Air of Superiority - 009 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Air of Superiority - 010 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Olafstead', timeout_ms=MAP_TIMEOUT_MS)))
    return steps

def _steps_unlock_mindbender() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Mindbender - 001 Travel', lambda: BT.Travel(target_map_name="Vlox's Falls", log=True)))
    steps.append(('Mindbender - 002 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(13999.00, 16113.00), 0x838101, log=True)))
    steps.append(('Mindbender - 003 Move', lambda: BT.Move(Vec2f(16198.73, 15155.11))))
    steps.append(('Mindbender - 004 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(15381,12281), target_map_name='Arbor Bay')))
    steps.append(('Mindbender - 005 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(14899.00, 12091.00), 0x838104)))
    steps.append(('Mindbender - 006 Route', lambda: BT.VanquishNode([(8432, 3986),(5623, 8718),(3850, 9318),(1114, 8111),(-576, 13157),(-2732, 10573),(-4062, 10552),(-3526, 13835),(-7432, 12634),(-10260, 12121),])))
    steps.append(('Mindbender - 007 Move And Dialog', lambda: BT.TargetAgentByName("Erff")))
    steps.append(('Mindbender - 008 Move And Dialog', lambda: BT.InteractTarget()))
    steps.append(('Mindbender - 009 Move And Dialog', lambda: BT.SendDialog(0x838104, log=True)))
    steps.append(('Mindbender - 010 Wait', lambda: BT.Wait(40000)))
    steps.append(('Mindbender - 011 Wait For Clear Enemies In Area', lambda: BT.WaitForClearEnemiesInArea(-9611.00, 12114.00, stable_clear_ms=360000, radius=3500, keep_player_near_center=True)))
    steps.append(('Mindbender - 012 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Mindbender - 016 Move', lambda: BT.Move(Vec2f(16198.73, 15155.11))))
    steps.append(('Mindbender - 014 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(13999.00, 16113.00), 0x838107, log=True)))
    steps.append(('Mindbender - 015 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))

    return steps

def _steps_unlock_asuran_scan() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Asuran Scan - 001 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Asuran Scan - 002 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837901, log=True)))
    steps.append(('Asuran Scan - 003 Travel', lambda: BT.Travel(target_map_name="Gadd's Encampment", log=True)))
    steps.append(('Asuran Scan - 004 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-9690, -19524), target_map_name='Sparkfly Swamp', timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.append((
        'Asuran Scan - 005 Search And Kill Facet',
        lambda: _facet_path_search_and_kill(
            name='Asuran Scan',
            model_id=ASURAN_SCAN_FACET_MODEL_ID,
            path=ASURAN_SCAN_FACET_PATH_01,
            spawn_point_indices=ASURAN_SCAN_FACET_SPAWN_INDICES,
            spawn_wait_ms=6_000,
            kill_timeout_ms=120_000,
            dead_confirm_ms=2_500,
        ),
    ))
    # Resign is unreachable unless Facet of Death death is confirmed.
    steps.append(('Asuran Scan - 006 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Asuran Scan - 007 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name="Gadd's Encampment", timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Asuran Scan - 008 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Asuran Scan - 009 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837907, log=True)))
    steps.append(('Asuran Scan - 010 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


def _steps_unlock_mental_block() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Mental Block - 001 Travel', lambda: BT.Travel(target_map_id=641, log=True)))
    steps.append(('Mental Block - 002 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=641, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Mental Block - 003 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837701, log=True)))
    steps.append(('Mental Block - 004 Travel', lambda: BT.Travel(target_map_id=639, log=True)))
    steps.append(('Mental Block - 005 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=639, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Mental Block - 006 Move', lambda: BT.Move(Vec2f(-22999, 6530), log=False)))
    steps.append(('Mental Block - 007 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=566, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append((
        'Mental Block - 008 Search And Kill Facet',
        lambda: _facet_path_search_and_kill(
            name='Mental Block',
            model_id=MENTAL_BLOCK_FACET_MODEL_ID,
            path=MENTAL_BLOCK_FACET_PATH_01,
            spawn_point_indices=MENTAL_BLOCK_FACET_SPAWN_INDICES,
            spawn_wait_ms=6_000,
            kill_timeout_ms=120_000,
            dead_confirm_ms=2_500,
        ),
    ))
    # Resign is unreachable unless Facet of Destruction death is confirmed.
    steps.append(('Mental Block - 009 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Mental Block - 010 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=639, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Mental Block - 011 Travel', lambda: BT.Travel(target_map_id=641, log=True)))
    steps.append(('Mental Block - 012 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=641, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Mental Block - 013 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837707, log=True)))
    steps.append(('Mental Block - 014 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


def _steps_unlock_pain_inverter() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Pain Inverter - 001 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Pain Inverter - 002 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837a01, log=True)))
    steps.append(('Pain Inverter - 003 Travel', lambda: BT.Travel(target_map_name="Vlox's Falls", log=True)))
    steps.append(('Pain Inverter - 004 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(15505.38, 12460.59), target_map_name='Arbor Bay', timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.append((
        'Pain Inverter - 005 Search And Kill Facet',
        lambda: _facet_path_search_and_kill(
            name='Pain Inverter',
            model_id=PAIN_INVERTER_FACET_MODEL_ID,
            path=PAIN_INVERTER_FACET_PATH_01,
            spawn_point_indices=PAIN_INVERTER_FACET_SPAWN_INDICES,
            spawn_wait_ms=6_000,
            kill_timeout_ms=120_000,
            dead_confirm_ms=2_500,
        ),
    ))
    # Resign is unreachable unless Facet of Spirit death is confirmed.
    steps.append(('Pain Inverter - 006 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Pain Inverter - 007 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name="Vlox's Falls", timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Pain Inverter - 008 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Pain Inverter - 009 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837a07, log=True)))
    steps.append(('Pain Inverter - 010 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


def _steps_unlock_radiation_field() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Radiation Field - 001 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Radiation Field - 002 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837801, log=True)))
    steps.append(('Radiation Field - 003 Travel', lambda: BT.Travel(target_map_name='Rata Sum', log=True)))
    steps.append(('Radiation Field - 004 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(20340, 16899), target_map_name='Riven Earth', timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.append((
        'Radiation Field - 005 Search And Kill Facet',
        lambda: _facet_path_search_and_kill(
            name='Radiation Field',
            model_id=RADIATION_FIELD_FACET_MODEL_ID,
            path=RADIATION_FIELD_FACET_PATH_01,
            spawn_point_indices=RADIATION_FIELD_FACET_SPAWN_INDICES,
            spawn_wait_ms=10_000,
            kill_timeout_ms=120_000,
            dead_confirm_ms=2_500,
        ),
    ))
    # Resign is unreachable unless Facet of Existence death is confirmed.
    steps.append(('Radiation Field - 006 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Radiation Field - 007 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Rata Sum', timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Radiation Field - 008 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Radiation Field - 009 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837807, log=True)))
    steps.append(('Radiation Field - 010 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


def _steps_unlock_smooth_criminal() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Smooth Criminal - 001 Travel', lambda: BT.Travel(target_map_id=641, log=True)))
    steps.append(('Smooth Criminal - 002 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=641, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Smooth Criminal - 003 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837c01, log=True)))
    steps.append(('Smooth Criminal - 004 Move', lambda: BT.Move(Vec2f(18781, -10477), log=False)))
    steps.append(('Smooth Criminal - 005 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Alcazia Tangle', timeout_ms=MAP_TIMEOUT_MS)))
    steps.append((
        'Smooth Criminal - 006 Search And Kill Facet',
        lambda: _facet_path_search_and_kill(
            name='Smooth Criminal',
            model_id=SMOOTH_CRIMINAL_FACET_MODEL_ID,
            path=SMOOTH_CRIMINAL_FACET_PATH_01,
            spawn_point_indices=SMOOTH_CRIMINAL_FACET_SPAWN_INDICES,
            spawn_wait_ms=6_000,
            kill_timeout_ms=120_000,
            dead_confirm_ms=2_500,
        ),
    ))
    # Resign is unreachable unless the helper has positively confirmed Facet death.
    steps.append(('Smooth Criminal - 007 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Smooth Criminal - 008 Wait', lambda: BT.Wait(3000)))
    steps.append(('Smooth Criminal - 009 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=641, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Smooth Criminal - 010 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837c07, log=True)))
    steps.append(('Smooth Criminal - 011 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps

def _steps_unlock_technobabble() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Technobabble - 001 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Technobabble - 002 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837b01, log=True)))
    steps.append(('Technobabble - 003 Travel', lambda: BT.Travel(target_map_name='Rata Sum', log=True)))
    steps.append(('Technobabble - 004 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-6062, -2688), target_map_name='Magus Stones', timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.append((
        'Technobabble - 005 Search And Kill Facet',
        lambda: _facet_path_search_and_kill(
            name='Technobabble',
            model_id=TECHNOBABBLE_FACET_MODEL_ID,
            path=TECHNOBABBLE_FACET_PATH_01,
            spawn_point_indices=TECHNOBABBLE_FACET_SPAWN_INDICES,
            spawn_wait_ms=6_000,
            kill_timeout_ms=120_000,
            dead_confirm_ms=2_500,
        ),
    ))
    # Resign is unreachable unless Facet of Illusions death is confirmed.
    steps.append(('Technobabble - 006 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Technobabble - 007 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Rata Sum', timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Technobabble - 008 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Technobabble - 009 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837b07, log=True)))
    steps.append(('Technobabble - 010 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


def _steps_unlock_deft_strike() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Deft Strike - 001 Travel', lambda: BT.Travel(target_map_name='Eye of the North outpost', log=True)))
    steps.append(('Deft Strike - 002 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-1856.0, 3073.0), 0x836401, log=True)))
    steps.append(('Deft Strike - 003 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-1856.0, 3073.0), 0x836404, log=True)))
    steps.append(('Deft Strike - 004 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-1856.0, 3073.0), 0x84, log=True)))
    steps.append(('Deft Strike - 005 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Mano a Norn-o', timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Deft Strike - 006 Move', lambda: BT.Move(Vec2f(-1470.06, 2672), log=False)))
    steps.append(('Deft Strike - 007 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-1856.0, 3073.0), 0x836407, log=True)))
    steps.append(('Deft Strike - 008 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


def _steps_unlock_ebon_battle_standard_of_honor() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Ebon Battle Standard of Honor - 001 Travel', lambda: BT.Travel(target_map_name='Longeyes Ledge', log=True)))
    steps.append(('Ebon Battle Standard of Honor - 002 Move', lambda: BT.Move(Vec2f(-21902, 12807), log=False)))
    steps.append(('Ebon Battle Standard of Honor - 003 Wait', lambda: BT.Wait(5000)))
    steps.append(('Ebon Battle Standard of Honor - 004 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-21141.81, 12378.68), 0x836003, log=True)))
    steps.append(('Ebon Battle Standard of Honor - 005 Wait', lambda: BT.Wait(1000)))
    steps.append(('Ebon Battle Standard of Honor - 006 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-21141.81, 12378.68), 0x836001, log=True)))
    steps.append(('Ebon Battle Standard of Honor - 007 Wait', lambda: BT.Wait(1000)))
    steps.extend(_movement_point_steps('Ebon Battle Standard of Honor - 008 Route', EBON_BATTLE_STANDARD_OF_HONOR_PATH_1_01))
    steps.append(('Ebon Battle Standard of Honor - 009 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Ebon Battle Standard of Honor - 010 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=651, timeout_ms=MAP_TIMEOUT_MS)))
    steps.extend(_movement_point_steps('Ebon Battle Standard of Honor - 011 Route', EBON_BATTLE_STANDARD_OF_HONOR_PATH_2_02))
    steps.append(('Ebon Battle Standard of Honor - 012 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Ebon Battle Standard of Honor - 013 Travel', lambda: BT.Travel(target_map_id=650, log=True)))
    steps.append(('Ebon Battle Standard of Honor - 014 Move', lambda: BT.Move(Vec2f(-21902, 12807), log=False)))
    steps.append(('Ebon Battle Standard of Honor - 015 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=649, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Ebon Battle Standard of Honor - 016 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-21141.81, 12378.68), 0x836007, log=True)))
    steps.append(('Ebon Battle Standard of Honor - 017 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


def _steps_unlock_ebon_escape() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append((
        'Ebon Escape - 001 Travel Eye of the North',
        lambda: BT.Travel(
            target_map_name='Eye of the North outpost',
            log=True,
        ),
    ))
    steps.append((
        'Ebon Escape - 002 Accept Quest',
        lambda: BT.MoveAndDialog(
            Vec2f(-1856.00, 3073.00),
            0x836901,
            log=True,
        ),
    ))
    steps.append((
        'Ebon Escape - 003 Enter Mission',
        lambda: BT.SendDialog(
            0x85,
            log=True,
        ),
    ))
    steps.append((
        'Ebon Escape - 004 Wait For Mission Map',
        lambda: BT.WaitForMapToChange(
            map_id=695,
            timeout_ms=MAP_TIMEOUT_MS,
        ),
    ))
    steps.append((
        'Ebon Escape - 005 Move To Defense Point',
        lambda: BT.Move(
            Vec2f(2070.34, 81.76),
            log=False,
        ),
    ))
    steps.append((
        'Ebon Escape - 006 Hold And Clear Area',
        lambda: BT.Wait(180_000),
    ))
    steps.append((
        'Ebon Escape - 007 Wait For Return To Eye',
        lambda: BT.WaitForMapLoad(
            map_name='Eye of the North outpost',
            timeout_ms=MAP_TIMEOUT_MS,
        ),
    ))
    steps.append((
        'Ebon Escape - 008 Claim Reward',
        lambda: BT.MoveAndDialog(
            Vec2f(-1856.00, 3073.00),
            0x836907,
            log=True,
        ),
    ))
    steps.append((
        'Ebon Escape - 009 Close Reward Window',
        lambda: BT.CancelSkillRewardWindow(),
    ))
    return steps


def _steps_unlock_ebon_vanguard_assassin_support() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Ebon Vanguard Assassin Support - 001 Travel', lambda: BT.Travel(target_map_name='Eye of the North outpost', log=True)))
    steps.append(('Ebon Vanguard Assassin Support - 002 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-1856.0, 3073.0), 0x836a01, log=True)))
    steps.append(('Ebon Vanguard Assassin Support - 003 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-1856.0, 3073.0), 0x836a04, log=True)))
    steps.append(('Ebon Vanguard Assassin Support - 004 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-1856.0, 3073.0), 0x86, log=True)))
    steps.append(('Ebon Vanguard Assassin Support - 005 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Service: Practice, Dummy', timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Ebon Vanguard Assassin Support - 006 Move', lambda: BT.Move(Vec2f(-1856.0, 3073.0), log=False)))
    steps.append(('Ebon Vanguard Assassin Support - 007 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Eye of the North outpost', timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Ebon Vanguard Assassin Support - 008 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-1856.0, 3073.0), 0x836a07, log=True)))
    steps.append(('Ebon Vanguard Assassin Support - 009 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


def _steps_unlock_winds() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Deft Strike - 001 Travel', lambda: BT.Travel(target_map_name='Eye of the North outpost', log=True)))
    steps.append(('Deft Strike - 002 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-1856.0, 3073.0), 0x835601, log=True)))
    steps.append(('Deft Strike - 003 Travel', lambda: BT.Travel(target_map_name="Gunnar's Hold", log=True)))
    steps.append(('Deft Strike - 004 Add heroes + builds', lambda: _winds_add_heroes_with_builds()))
    steps.append(('Deft Strike - 005 Wait', lambda: BT.Wait(2000)))
    steps.append(('Deft Strike - 006 Add Henchies', lambda: _winds_add_henchies()))
    steps.append(('Deft Strike - 007 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(15183.199218, -6381.958984), target_map_name='Norrhart Domains', timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.extend(_movement_point_steps('Deft Strike - 008 Route', WINDS_PATH_01))
    steps.append(('Deft Strike - 009 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Deft Strike - 010 Travel', lambda: BT.Travel(target_map_name='Eye of the North outpost', log=True)))
    steps.append(('Deft Strike - 011 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-1856.0, 3073.0), 0x835607, log=True)))
    steps.append(('Deft Strike - 012 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


def _steps_unlock_i_am_unstoppable() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('IAU:TAKE_ANYTHING_YOU_CAN_DO', lambda: BT.Succeeder(name='IAU:TAKE_ANYTHING_YOU_CAN_DO')))
    steps.append(('I Am Unstoppable! - 001 Travel', lambda: BT.Travel(target_map_name='Sifhalla', log=True)))
    steps.append(('I Am Unstoppable! - 002 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=643, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('I Am Unstoppable! - 003 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(14380, 23874), 0x833e01, log=True)))
    steps.append(('IAU:HUNT_AVARR_AND_WHITEOUT', lambda: BT.Succeeder(name='IAU:HUNT_AVARR_AND_WHITEOUT')))
    steps.append(('I Am Unstoppable! - 004 Travel', lambda: BT.Travel(target_map_name='Sifhalla', log=True)))
    steps.append(('I Am Unstoppable! - 005 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=643, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('I Am Unstoppable! - 006 Move', lambda: BT.Move(Vec2f(14682, 22900), log=False)))
    steps.append(('I Am Unstoppable! - 007 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(17000, 22872), target_map_id=546, timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.append(('I Am Unstoppable! - 008 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=546, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('I Am Unstoppable! - 009 Move', lambda: BT.Move(Vec2f(-9431, -20124), log=False)))
    steps.append(('I Am Unstoppable! - 010 Move', lambda: BT.Move(Vec2f(-8441, -13685), log=False)))
    steps.append(('I Am Unstoppable! - 011 Move', lambda: BT.Move(Vec2f(-9743, -6744), log=False)))
    steps.append(('I Am Unstoppable! - 012 Move', lambda: BT.Move(Vec2f(-10672, 4815), log=False)))
    steps.append(('I Am Unstoppable! - 013 Move', lambda: BT.Move(Vec2f(-8464, 17239), log=False)))
    steps.append(('I Am Unstoppable! - 014 Move', lambda: BT.Move(Vec2f(-11700, 24101), log=False)))
    steps.append(('I Am Unstoppable! - 015 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('I Am Unstoppable! - 016 Move', lambda: BT.Move(Vec2f(-8464, 17239), log=False)))
    steps.append(('I Am Unstoppable! - 017 Move', lambda: BT.Move(Vec2f(-638, 17801), log=False)))
    steps.append(('I Am Unstoppable! - 018 Move', lambda: BT.Move(Vec2f(-933, 15368), log=False)))
    steps.append(('I Am Unstoppable! - 019 Wait', lambda: BT.Wait(6000)))
    steps.append(('I Am Unstoppable! - 020 Move', lambda: BT.Move(Vec2f(-1339, 22089), log=False)))
    steps.append(('I Am Unstoppable! - 021 Wait', lambda: BT.Wait(5000)))
    steps.append(('IAU:FRAGMENT_OF_ANTIQUITIES', lambda: BT.Succeeder(name='IAU:FRAGMENT_OF_ANTIQUITIES')))
    steps.append(('I Am Unstoppable! - 022 Travel', lambda: BT.Travel(target_map_name='Sifhalla', log=True)))
    steps.append(('I Am Unstoppable! - 023 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=643, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Fragment of Antiquities - 024 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(8832, 23870), target_map_id=513, timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.append(('Fragment of Antiquities - 025 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=513, timeout_ms=MAP_TIMEOUT_MS)))
    steps.extend(_movement_point_steps('Fragment of Antiquities - 026 Route', DRAKKAR_TO_REMLOK_ROUTE_XY[:-2]))
    steps.append(('Fragment of Antiquities - 027 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-10926, 24732), 0x832901, log=True)))
    steps.append(('Fragment of Antiquities - 028 Move', lambda: BT.Move(Vec2f(-11293.05, 24868.94), log=False)))
    steps.append(('Fragment of Antiquities - 029 Move', lambda: BT.Move(Vec2f(-11603.0, 24975.0), log=False)))
    steps.append(('Fragment of Antiquities - 030 Move', lambda: BT.Move(Vec2f(-11763.68, 25412.23), log=False)))
    steps.append(('Fragment of Antiquities - 031 Move', lambda: BT.Move(Vec2f(-11904.67, 25896.55), log=False)))
    steps.append(('Fragment of Antiquities - 032 Move', lambda: BT.Move(Vec2f(-12009.97, 26331.78), log=False)))
    steps.append(('Fragment of Antiquities - 033 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-12138, 26829), target_map_id=628, timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.append(('Fragment of Antiquities - 034 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=628, timeout_ms=MAP_TIMEOUT_MS)))
    steps.extend(_movement_point_steps('Fragment of Antiquities - 035 Route', SEPULCHRE_PROOF_OF_STRENGTH_ROUTE_XY))
    steps.append(('Fragment of Antiquities - 036 Wait', lambda: BT.Wait(1500)))
    steps.extend(_movement_point_steps('Fragment of Antiquities - 037 Route', SEPULCHRE_LEVEL1_FRAGMENT_ROUTE_XY))
    steps.append(('Fragment of Antiquities - 038 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('IAU:CLAIM_ANYTHING_YOU_CAN_DO', lambda: BT.Succeeder(name='IAU:CLAIM_ANYTHING_YOU_CAN_DO')))
    steps.append(('Fragment of Antiquities - 039 Travel', lambda: BT.Travel(target_map_name='Sifhalla', log=True)))
    steps.append(('Fragment of Antiquities - 040 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=643, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Fragment of Antiquities - 041 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(14380, 23968), 0x833e07, log=True)))
    steps.append(('IAU:COLD_AS_ICE', lambda: BT.Succeeder(name='IAU:COLD_AS_ICE')))
    steps.append(('Fragment of Antiquities - 042 Travel', lambda: BT.Travel(target_map_name='Sifhalla', log=True)))
    steps.append(('Fragment of Antiquities - 043 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=643, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Fragment of Antiquities - 044 Spawn Bonus Items', lambda: BT.SpawnBonusItems(log=True)))
    steps.append(('Fragment of Antiquities - 045 Equip Item', lambda: BT.EquipItemByModelID(ModelID.Bonus_Nevermore_Flatbow.value, log=True)))
    steps.append(('Fragment of Antiquities - 046 Equip Item', lambda: BT.EquipItemByModelID(6515, log=True)))
    steps.append(('Fragment of Antiquities - 047 Equip Skill Bar', lambda: _iau_equip_skillbar()))
    steps.append(('Fragment of Antiquities - 048 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(14380, 23968), 0x834401, log=True)))
    steps.append(('Fragment of Antiquities - 049 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(14380, 23968), 0x85, log=True)))
    steps.append(('Fragment of Antiquities - 050 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=690, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Fragment of Antiquities - 051 Wait', lambda: BT.Wait(5000)))
    steps.append(('Fragment of Antiquities - 052 Move', lambda: BT.Move(Vec2f(14553, 23043), log=False)))
    steps.append(('Fragment of Antiquities - 053 Wait', lambda: BT.Wait(2000)))
    steps.append(('Fragment of Antiquities - 054 Use Skill', lambda: BT.CastSkillID(skill_id=114, log=True)))
    steps.append(('Fragment of Antiquities - 055 Wait Until On Combat', lambda: BT.WaitUntilOnCombat(timeout_ms=120_000)))
    steps.append(('Fragment of Antiquities - 056 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Fragment of Antiquities - 057 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Fragment of Antiquities - 058 Wait', lambda: BT.Wait(20000)))
    steps.append(('Fragment of Antiquities - 059 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=643, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('IAU:CLAIM_FINAL_REWARD', lambda: BT.Succeeder(name='IAU:CLAIM_FINAL_REWARD')))
    steps.append(('Fragment of Antiquities - 060 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(14380, 23968), 0x834407, log=True)))
    steps.append(('I Am Unstoppable! - 061 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


def _steps_unlock_you_move_like_a_dwarf() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('You Move Like a Dwarf! - 001 Travel', lambda: BT.Travel(target_map_name='Sifhalla', log=True)))
    steps.append(('You Move Like a Dwarf! - 002 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=643, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('You Move Like a Dwarf! - 003 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(14380, 23968), 0x833a01, log=True)))
    steps.append(('You Move Like a Dwarf! - 004 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(8832, 23870), target_map_id=513, timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.append(('You Move Like a Dwarf! - 005 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=513, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('You Move Like a Dwarf! - 006 Move', lambda: BT.Move(Vec2f(11434, 19708), log=False)))
    steps.append(('You Move Like a Dwarf! - 007 Move', lambda: BT.Move(Vec2f(14164, 2682), log=False)))
    steps.append(('You Move Like a Dwarf! - 008 Move', lambda: BT.Move(Vec2f(9435, -5806), log=False)))
    steps.append(('You Move Like a Dwarf! - 009 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('You Move Like a Dwarf! - 010 Move', lambda: BT.Move(Vec2f(1914, -6963), log=False)))
    steps.append(('You Move Like a Dwarf! - 011 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('You Move Like a Dwarf! - 012 Move', lambda: BT.Move(Vec2f(4735, -14202), log=False)))
    steps.append(('You Move Like a Dwarf! - 013 Move', lambda: BT.Move(Vec2f(5752, -15236), log=False)))
    steps.append(('You Move Like a Dwarf! - 014 Move', lambda: BT.Move(Vec2f(8924, -15922), log=False)))
    steps.append(('You Move Like a Dwarf! - 015 Move', lambda: BT.Move(Vec2f(14134, -16744), log=False)))
    steps.append(('You Move Like a Dwarf! - 016 Move', lambda: BT.Move(Vec2f(12581, -19343), log=False)))
    steps.append(('You Move Like a Dwarf! - 017 Move', lambda: BT.Move(Vec2f(12702, -23855), log=False)))
    steps.append(('You Move Like a Dwarf! - 018 Move', lambda: BT.Move(Vec2f(13952, -23063), log=False)))
    steps.append(('You Move Like a Dwarf! - 019 Wait', lambda: BT.Wait(45000)))
    steps.append(('You Move Like a Dwarf! - 020 Travel', lambda: BT.Travel(target_map_name='Sifhalla', log=True)))
    steps.append(('You Move Like a Dwarf! - 021 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=643, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('You Move Like a Dwarf! - 022 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(14380, 23968), 0x833a07, log=True)))
    steps.append(('You Move Like a Dwarf! - 023 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


def _steps_unlock_feel_no_pain() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Feel No Pain - 001 Travel', lambda: BT.Travel(target_map_name='Olafstead', log=True)))
    steps.append(('Feel No Pain - 002 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(90.0, -749.0), 0x835201, log=True)))
    steps.append(('Feel No Pain - 003 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(90.0, -749.0), 0x84, log=True)))
    steps.append(('Feel No Pain - 004 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='The Great Norn Alemoot', timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Feel No Pain - 005 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(12602.0, -6210.0), 0x85, log=True)))
    steps.append(('Feel No Pain - 006 Move And Interact Gadget', lambda: BT.MoveAndInteractWithGadget(pos=Vec2f(12727.0, -6612.0), log=True)))
    steps.append(('Feel No Pain - 007 Move And Interact Gadget', lambda: BT.MoveAndInteractWithGadget(pos=Vec2f(12701.0, -6523.0), log=True)))
    steps.append(('Feel No Pain - 008 Move And Interact Gadget', lambda: BT.MoveAndInteractWithGadget(pos=Vec2f(10109.0, -8707.0), log=True)))
    steps.append(('Feel No Pain - 009 Move', lambda: BT.Move(Vec2f(10750.13, -9616.31), log=False)))
    steps.append(('Feel No Pain - 010 Move And Interact Gadget', lambda: BT.MoveAndInteractWithGadget(pos=Vec2f(10109.0, -8707.0), log=True)))
    steps.append(('Feel No Pain - 011 Move', lambda: BT.Move(Vec2f(10750.13, -9616.31), log=False)))
    steps.append(('Feel No Pain - 012 Move And Interact Gadget', lambda: BT.MoveAndInteractWithGadget(pos=Vec2f(10109.0, -8707.0), log=True)))
    steps.append(('Feel No Pain - 013 Move', lambda: BT.Move(Vec2f(10750.13, -9616.31), log=False)))
    steps.append(('Feel No Pain - 014 Move', lambda: BT.Move(Vec2f(12727.0, -6612.0), log=False)))
    steps.append(('Feel No Pain - 015 Move And Interact Gadget', lambda: BT.MoveAndInteractWithGadget(pos=Vec2f(12727.0, -6612.0), log=True)))
    steps.append(('Feel No Pain - 016 Move And Interact Gadget', lambda: BT.MoveAndInteractWithGadget(pos=Vec2f(12701.0, -6523.0), log=True)))
    steps.extend(_movement_point_steps('Feel No Pain - 017 Route', FEEL_NO_PAIN_PATH_01))
    steps.append(('Feel No Pain - 018 Move', lambda: BT.Move(Vec2f(12727.0, -6612.0), log=False)))
    steps.append(('Feel No Pain - 019 Move And Interact Gadget', lambda: BT.MoveAndInteractWithGadget(pos=Vec2f(12727.0, -6612.0), log=True)))
    steps.append(('Feel No Pain - 020 Move And Interact Gadget', lambda: BT.MoveAndInteractWithGadget(pos=Vec2f(12701.0, -6523.0), log=True)))
    steps.append(('Feel No Pain - 021 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(12602.0, -6210.0), 0x835207, log=True)))
    steps.append(('Feel No Pain - 022 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


def _steps_unlock_dwarven_stability() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Dwarven Stability - 001 Travel', lambda: BT.Travel(target_map_name='Sifhalla', log=True)))
    steps.append(('Dwarven Stability - 002 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=643, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Dwarven Stability - 003 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(12009, 24726), 0x837e03, log=True)))
    steps.append(('Dwarven Stability - 004 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(12009, 24726), 0x837e01, log=True)))
    steps.append(('Dwarven Stability - 005 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(13583, 18781), target_map_id=513, timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.append(('Dwarven Stability - 006 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=513, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Dwarven Stability - 007 Move', lambda: BT.Move(Vec2f(15159, 12506), log=False)))
    steps.append(('Dwarven Stability - 008 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Dwarven Stability - 009 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Dwarven Stability - 010 Wait', lambda: BT.Wait(3000)))
    steps.append(('Dwarven Stability - 011 Wait For Map Change', lambda: BT.WaitForMapToChange(map_id=643, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Dwarven Stability - 012 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(12009, 24726), 0x837e07, log=True)))
    steps.append(('Dwarven Stability - 013 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


def _steps_unlock_great_dwarf_weapon() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Great Dwarf Weapon - 001 Travel', lambda: BT.Travel(target_map_id=652, log=True)))
    steps.append(('Great Dwarf Weapon - 002 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-25,4723), target_map_id=625, timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.append(('Great Dwarf Weapon - 003 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-3416.00, 17460.00), 0x838401, log=True)))
    steps.append(('Great Dwarf Weapon - 004 Move And Dialog', lambda: BT.SendDialog(0x84)))
    steps.append(('Great Dwarf Weapon - 005 Wait For Map Load', lambda: BT.WaitForMapLoad(717)))
    steps.append(('Great Dwarf Weapon - 006 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-3416.00, 17460.00), 0x838404, log=True)))
    steps.append(('Great Dwarf Weapon - 007 Move', lambda: BT.Move(Vec2f(-2297.21, 15809.95), log=False)))
    steps.append(('Great Dwarf Weapon - 008 Clear Area', lambda: BT.ClearEnemiesInArea(Vec2f(-2297.21, 15809.95),radius=Range.Compass.value, log=True)))
    steps.append(('Great Dwarf Weapon - 009 Wait for total cleanup', lambda: BT.WaitForClearEnemiesInArea(-2297.21, 15809.95, radius=Range.Compass.value, stable_clear_ms=120_000)))
    steps.append(('Great Dwarf Weapon - 010 Wait for map change', lambda: BT.WaitForMapToChange(map_id=625)))
    steps.append(('Great Dwarf Weapon - 011 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-3416.00, 17460.00), 0x838407, log=True)))
    steps.append(('Great Dwarf Weapon - 012 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps

def _steps_unlock_by_urals_hammer() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Great Dwarf Weapon - 001 Travel', lambda: BT.Travel(target_map_id=652, log=True)))
    steps.append(('Great Dwarf Weapon - 002 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-25,4723), target_map_id=625, timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.append(('Great Dwarf Weapon - 003 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-3416.00, 17460.00), 0x838401, log=True)))
    steps.append(('Great Dwarf Weapon - 004 Move And Dialog', lambda: BT.SendDialog(0x84)))
    steps.append(('Great Dwarf Weapon - 005 Wait For Map Load', lambda: BT.WaitForMapLoad(717)))
    steps.append(('Great Dwarf Weapon - 006 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-3416.00, 17460.00), 0x838404, log=True)))
    steps.append(('Great Dwarf Weapon - 007 Move', lambda: BT.Move(Vec2f(-2297.21, 15809.95), log=False)))
    steps.append(('Great Dwarf Weapon - 008 Clear Area', lambda: BT.ClearEnemiesInArea(Vec2f(-2297.21, 15809.95),radius=Range.Compass.value, log=True)))
    steps.append(('Great Dwarf Weapon - 009 Wait for total cleanup', lambda: BT.WaitForClearEnemiesInArea(-2297.21, 15809.95, radius=Range.Compass.value, stable_clear_ms=120_000)))
    steps.append(('Great Dwarf Weapon - 010 Wait for map change', lambda: BT.WaitForMapToChange(map_id=625)))
    steps.append(('Great Dwarf Weapon - 011 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-3416.00, 17460.00), 0x838407, log=True)))
    steps.append(('Great Dwarf Weapon - 012 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


def _steps_unlock_great_dwarf_armor() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Great Dwarf Armor - 001 Travel', lambda: BT.Travel(target_map_id=652, log=True)))
    steps.append(('Great Dwarf Armor - 002 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-25,4723), target_map_id=625, timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.append(('Great Dwarf Armor - 003 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-3416.00, 17460.00), 0x834501, log=True)))
    steps.append(('Great Dwarf Armor - 004 Travel', lambda: BT.Travel(643)))
    steps.append(('Great Dwarf Armor - 005 Exit', lambda : BT.MoveAndExitMap(Vec2f(9656,23869),target_map_id=513 )))
    steps.append(('Great Dwarf Armor - 006 Vanquish', lambda : BT.VanquishNode([(3809,22487),(2807,17322),(234,15756),(-2925,13265),(-6376,8698),(-8987,8005),(-9265,5937),(-9522,4043),(-8518,2346),(-11257,1443),(-12605,4127),(-12674,428),])))
    steps.append(('Great Dwarf Armor - 007 Travel', lambda: BT.Travel(target_map_id=652, log=True)))
    steps.append(('Great Dwarf Armor - 008 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-25,4723), target_map_id=625, timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.append(('Great Dwarf Armor - 009 Move And Dialog', lambda: BT.MoveAndAutoDialog(Vec2f(-3416.00, 17460.00),0, log=True)))

    steps.append(('Great Dwarf Armor - 010 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


ALKAR_DESTROYER_POSITION = (-14690.0, 17456.0)


def _use_alkars_concoction() -> BehaviorTree:
    # Confirmed from runtime log after a successful manual jump.
    ALKAR_CONCOCTION_MODEL_ID = 25739

    state = {
        "started_ms": 0.0,
        "last_log_ms": 0.0,
    }

    def _find_concoction_by_model_id() -> int:
        try:
            item_id = int(
                GLOBAL_CACHE.Inventory.GetFirstModelID(ALKAR_CONCOCTION_MODEL_ID) or 0
            )
            if item_id > 0:
                return item_id
        except Exception:
            pass

        # Fallback: scan carried bags directly, still without relying on item names.
        try:
            bag_list = GLOBAL_CACHE.ItemArray.CreateBagList(1, 2, 3, 4)
            item_array = GLOBAL_CACHE.ItemArray.GetItemArray(bag_list)
            for raw_item_id in item_array:
                item_id = int(raw_item_id)
                try:
                    if int(GLOBAL_CACHE.Item.GetModelID(item_id) or 0) == ALKAR_CONCOCTION_MODEL_ID:
                        return item_id
                except Exception:
                    continue
        except Exception:
            pass

        return 0

    def _use(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        import time

        now_ms = time.monotonic() * 1000.0
        if state["started_ms"] <= 0.0:
            state["started_ms"] = now_ms

        item_id = _find_concoction_by_model_id()

        if item_id <= 0:
            if now_ms - state["last_log_ms"] >= 2000.0:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"Alkar: waiting for concoction model_id={ALKAR_CONCOCTION_MODEL_ID}",
                    PySystem.Console.MessageType.Warning,
                )
                state["last_log_ms"] = now_ms

            if now_ms - state["started_ms"] >= 10000.0:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"Alkar: concoction model_id={ALKAR_CONCOCTION_MODEL_ID} not found after 10s",
                    PySystem.Console.MessageType.Error,
                )
                state["started_ms"] = 0.0
                state["last_log_ms"] = 0.0
                return BehaviorTree.NodeState.FAILURE

            return BehaviorTree.NodeState.RUNNING

        try:
            PySystem.Console.Log(
                MODULE_NAME,
                f"Alkar: using concoction item_id={item_id}, model_id={ALKAR_CONCOCTION_MODEL_ID}",
                PySystem.Console.MessageType.Info,
            )

            GLOBAL_CACHE.Inventory.UseItem(item_id)

            state["started_ms"] = 0.0
            state["last_log_ms"] = 0.0
            return BehaviorTree.NodeState.SUCCESS

        except Exception as exc:
            PySystem.Console.Log(
                MODULE_NAME,
                f"Alkar: failed to use concoction: {exc}",
                PySystem.Console.MessageType.Error,
            )
            state["started_ms"] = 0.0
            state["last_log_ms"] = 0.0
            return BehaviorTree.NodeState.FAILURE

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Alkar - Use Concoction",
            action_fn=_use,
            aftercast_ms=1500,
        )
    )

def _clear_target() -> BehaviorTree:
    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        Player.ChangeTarget(0)
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Alkar - Clear Target",
            action_fn=_tick,
            aftercast_ms=250,
        )
    )


def _move_to_nearest_destroyer(
    stop_distance: float = 150.0,
    timeout_ms: int = 15_000,
) -> BehaviorTree:
    """Follow the nearest living enemy without ever targeting it.

    In Glint's Challenge at this point of the quest the hostile agents are
    Destroyers, so the nearest living enemy is the desired acid target.
    """
    state = {
        "started_ms": 0.0,
        "last_move_ms": 0.0,
        "last_enemy_id": 0,
    }

    def _reset() -> None:
        state["started_ms"] = 0.0
        state["last_move_ms"] = 0.0
        state["last_enemy_id"] = 0

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        now_ms = time.monotonic() * 1000.0
        if state["started_ms"] <= 0.0:
            state["started_ms"] = now_ms

        # HeroAI is disabled here, but keep the player explicitly untargeted.
        if int(Player.GetTargetID() or 0) != 0:
            Player.ChangeTarget(0)

        px, py = Player.GetXY()
        living_enemies: list[int] = []

        for raw_agent_id in AgentArray.GetEnemyArray():
            agent_id = int(raw_agent_id)
            try:
                if Agent.IsLiving(agent_id) and not Agent.IsDead(agent_id):
                    living_enemies.append(agent_id)
            except Exception:
                continue

        if not living_enemies:
            if now_ms - state["started_ms"] >= float(timeout_ms):
                PySystem.Console.Log(
                    MODULE_NAME,
                    "Alkar: no living Destroyer found near the approach area.",
                    PySystem.Console.MessageType.Error,
                )
                _reset()
                return BehaviorTree.NodeState.FAILURE
            return BehaviorTree.NodeState.RUNNING

        def _distance_sq(agent_id: int) -> float:
            ex, ey = Agent.GetXY(agent_id)
            dx = float(ex) - float(px)
            dy = float(ey) - float(py)
            return dx * dx + dy * dy

        enemy_id = min(living_enemies, key=_distance_sq)
        ex, ey = Agent.GetXY(enemy_id)
        dx = float(ex) - float(px)
        dy = float(ey) - float(py)
        distance_sq = dx * dx + dy * dy

        if distance_sq <= float(stop_distance) * float(stop_distance):
            PySystem.Console.Log(
                MODULE_NAME,
                f"Alkar: reached nearest Destroyer agent_id={enemy_id} within {stop_distance:.0f} units.",
                PySystem.Console.MessageType.Info,
            )
            Player.ChangeTarget(0)
            _reset()
            return BehaviorTree.NodeState.SUCCESS

        # Refresh the destination while the Destroyer moves, without interacting
        # with or selecting it.
        if (
            enemy_id != int(state["last_enemy_id"])
            or now_ms - float(state["last_move_ms"]) >= 250.0
        ):
            Player.Move(float(ex), float(ey))
            state["last_move_ms"] = now_ms
            state["last_enemy_id"] = enemy_id

        if now_ms - state["started_ms"] >= float(timeout_ms):
            PySystem.Console.Log(
                MODULE_NAME,
                f"Alkar: timed out moving toward nearest Destroyer agent_id={enemy_id}.",
                PySystem.Console.MessageType.Error,
            )
            Player.ChangeTarget(0)
            _reset()
            return BehaviorTree.NodeState.FAILURE

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Alkar - Move To Nearest Destroyer",
            action_fn=_tick,
            aftercast_ms=0,
        )
    )


def _steps_unlock_alkar_alchemical_acid() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Alkar - 001 Travel', lambda: BT.Travel(target_map_id=652, log=True)))
    steps.append(('Alkar - 002 Take Quest', lambda: BT.MoveAndDialog(Vec2f(-5.00, -911.00), 0x835C01, log=True)))
    steps.append(('Alkar - 003 Enter Mission', lambda: BT.MoveAndDialog(Vec2f(2480.00, 3586.00), 0x86, log=True)))
    steps.append(('Alkar - 004 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=37, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Alkar - 005 Disable HeroAI', lambda: BottingTree.DisableHeroAITree(reset_runtime=True)))
    steps.append(('Alkar - 006 Wait HeroAI Off', lambda: BT.Wait(500)))
    steps.append(('Alkar - 007 Clear Target', lambda: _clear_target()))
    steps.append(('Alkar - 008 Wait For Destroyers', lambda: BT.Wait(50000)))
    steps.append(('Alkar - 009 Clear Target Before Move', lambda: _clear_target()))
    steps.append(('Alkar - 010 Move Near Destroyers', lambda: BT.Move(Vec2f(-2718.10, -88.09), pause_on_combat=False, log=True)))
    steps.append(('Alkar - 011 Move To Nearest Destroyer', lambda: _move_to_nearest_destroyer(stop_distance=150.0, timeout_ms=15_000)))
    steps.append(('Alkar - 012 Use Concoction', lambda: _use_alkars_concoction()))
    steps.append(('Alkar - 013 Wait For Quest Update', lambda: BT.Wait(2000)))
    steps.append(('Alkar - 014 Enable HeroAI', lambda: BottingTree.EnableHeroAITree(reset_runtime=True)))
    steps.append(('Alkar - 015 Wait For Return', lambda: BT.WaitForMapToChange(map_id=652, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Alkar - 016 Reward', lambda: BT.MoveAndDialog(Vec2f(-5.00, -911.00), 0x835C07, log=True)))
    steps.append(('Alkar - 017 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


DESTROYER_CORE_MODEL_ID = 27033
DESTROYER_CORES_REQUIRED = 3


def _inventory_model_quantity(model_id: int) -> int:
    """Return the total carried quantity of a model across bags 1-4."""
    total = 0

    try:
        bags = GLOBAL_CACHE.ItemArray.CreateBagList(1, 2, 3, 4)
        item_array = GLOBAL_CACHE.ItemArray.GetItemArray(bags)
    except Exception:
        return 0

    for raw_item_id in item_array:
        item_id = int(raw_item_id)

        try:
            if int(GLOBAL_CACHE.Item.GetModelID(item_id) or 0) != int(model_id):
                continue

            quantity = int(Item.Properties.GetQuantity(item_id) or 0)
            total += max(0, quantity)
        except Exception:
            continue

    return total


def _lod_has_required_destroyer_cores(
    required: int = DESTROYER_CORES_REQUIRED,
) -> BehaviorTree:
    """SUCCESS when the player carries at least the required Destroyer Cores."""

    def _check() -> BehaviorTree.NodeState:
        quantity = _inventory_model_quantity(DESTROYER_CORE_MODEL_ID)

        PySystem.Console.Log(
            MODULE_NAME,
            f"Light of Deldrimor: Destroyer Cores {quantity}/{required}.",
            PySystem.Console.MessageType.Info,
        )

        return (
            BehaviorTree.NodeState.SUCCESS
            if quantity >= int(required)
            else BehaviorTree.NodeState.FAILURE
        )

    return BehaviorTree(
        BehaviorTree.ConditionNode(
            name=f"LoD - Have {required} Destroyer Cores",
            condition_fn=_check,
        )
    )


def _lod_farm_one_destroyer_core_run() -> BehaviorTree:
    """
    Run one mission cycle.

    The final Failer is intentional: after returning to map 652 it forces the
    surrounding RepeaterUntilSuccessNode to restart from the inventory check.
    """
    return BT.Sequence(
        name="LoD - Farm One Destroyer Core Run",
        children=[
            BT.MoveAndDialog(
                Vec2f(2480.00, 3586.00),
                0x86,
                log=True,
            ),
            BT.WaitForMapLoad(
                map_id=37,
                timeout_ms=MAP_TIMEOUT_MS,
            ),
            BT.Move(
                Vec2f(-4531.36, 160.18),
                log=True,
            ),
            BT.WaitForClearEnemiesInArea(
                -4531.36,
                160.18,
                stable_clear_ms=60000,
            ),
            BT.WaitForMapToChange(
                map_id=652,
                timeout_ms=MAP_TIMEOUT_MS,
            ),
            BT.Wait(1000),

            # One run is complete, but the overall job is not considered
            # successful until the next inventory check sees 3+ cores.
            BT.Failer(name="LoD - Recheck Destroyer Cores"),
        ],
    )


def _lod_collect_destroyer_cores_until_ready() -> BehaviorTree:
    """
    Check inventory first.

    3+ cores -> SUCCESS immediately.
    <3 cores -> run mission once -> FAILURE -> repeater checks inventory again.
    """
    check_or_farm = BehaviorTree(
        BehaviorTree.SelectorNode(
            name="LoD - Check Cores Or Farm",
            children=[
                _lod_has_required_destroyer_cores().root,
                _lod_farm_one_destroyer_core_run().root,
            ],
        )
    )

    return BehaviorTree(
        BehaviorTree.RepeaterUntilSuccessNode(
            name="LoD - Farm Until 3 Destroyer Cores",
            child=check_or_farm.root,
            timeout_ms=0,
        )
    )


def _steps_unlock_light_of_deldrimor() -> list[PlannerStep]:
    steps: list[PlannerStep] = []

    steps.append(('LoD - 001 Travel', lambda: BT.Travel(target_map_id=652, log=True)))
    steps.append(('LoD - 002 Take Quest', lambda: BT.MoveAndDialog(Vec2f(-5.00, -911.00), 0x835B01, log=True)))
    steps.append(('LoD - 003 Add Destroyer Core To LootFilter', lambda: BT.AddModelToLootWhitelist(DESTROYER_CORE_MODEL_ID)))
    steps.append(('LoD - 004 Collect 3 Destroyer Cores', lambda: _lod_collect_destroyer_cores_until_ready()))
    steps.append(('LoD - 005 Reward', lambda: BT.MoveAndDialog(Vec2f(-5.00, -911.00), 0x835B07, log=True)))

    steps.append(('LoD - 006 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps

def steps_unlock_breath_of_the_great_dwarf() -> list[PlannerStep]:
    steps: list[PlannerStep] = []

    steps.append(('LoD - 001 Travel', lambda: BT.Travel(target_map_id=652, log=True)))
    steps.append(('LoD - 002 Take Quest', lambda: BT.MoveAndDialog(Vec2f(-5.00, -911.00), 0x835B01, log=True)))
    steps.append(('LoD - 003 Add Destroyer Core To LootFilter', lambda: BT.AddModelToLootWhitelist(DESTROYER_CORE_MODEL_ID)))
    steps.append(('LoD - 004 Collect 3 Destroyer Cores', lambda: _lod_collect_destroyer_cores_until_ready()))
    steps.append(('LoD - 005 Reward', lambda: BT.MoveAndDialog(Vec2f(-5.00, -911.00), 0x835B07, log=True)))

    steps.append(('LoD - 006 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps

# ---------------------------------------------------------------------------
# Skill registry / UI
# ---------------------------------------------------------------------------

RAW_SKILLS = [('air_of_superiority',
  'Air of Superiority',
  'Asura',
  'Unlock_air_of_superiority',
  'Skill. (20...30 seconds). Gain a random Asura benefit every time you earn experience from killing an enemy.'),
 ('asuran_scan',
  'Asuran Scan',
  'Asura',
  'Unlock_asuran_scan',
  'Hex Spell. (9...12 seconds.) You cannot miss target foe. If you kill this foe, you lose 5% Death Penalty.'),
 ('Mental_Block',
  'Mental Block',
  'Asura',
  'Unlock_mental_block',
  'Enchantment Spell. (5...11 seconds.) You have a 50% chance to block. Renewal: every time an enemy hits you.'),
 ('mindbender',
  'Mindbender',
  'Asura',
  'Unlock_mindbender',
  'Enchantment Spell. (10...16 seconds.) You move 20...33% faster and cast Spells 20% faster.'),
 ('pain_inverter',
  'Pain Inverter',
  'Asura',
  'Unlock_pain_inverter',
  'Hex Spell. (6...10 seconds.) Deals 100...140% of the damage (maximum 80) back to target foe every time it does damage.'),
 ('radiation_field',
  'Radiation Field',
  'Asura',
  'Unlock_radiation_field',
  'Ward Spell. (5 seconds.) Causes -4...6 Health degeneration to foes in the area. End effect: inflicts Disease condition (12...20 '
  'seconds) to foes in the area.'),
 ('smooth_criminal',
  'Smooth Criminal',
  'Asura',
  'Unlock_smooth_criminal',
  'Spell. (10...20 seconds.) Disables one Spell. This skill becomes that Spell. You gain 5...10 Energy.'),
 ('summon_ice_imp',
  'Summon Ice Imp',
  'Asura',
  'Unlock_summon_ice_imp',
  'Spell. Summon a level 14...20 Ice Imp (40...60 lifespan) that has Ice Spikes. Only 1 Asura Summon can be active a time.'),
 ('summon_mursaat',
  'Summon Mursaat',
  'Asura',
  'Unlock_summon_mursaat',
  'Spell. Summon a level 14...20 Mursaat (40...60 lifespan) that has Enervating Charge. Only 1 Asura Summon can be active a time.'),
 ('summon_naga_shaman',
  'Summon Naga Shaman',
  'Asura',
  'Unlock_summon_naga_shaman',
  'Spell. Summon a level 14...20 Naga Shaman (40...60 lifespan) that has Stoning. Only 1 Asura Summon can be active a time.'),
 ('summon_ruby_djinn',
  'Summon Ruby Djinn',
  'Asura',
  'Unlock_summon_ruby_djinn',
  'Spell. Summon a level 14...20 Ruby Djinn (40...60 lifespan) that has Immolate. Only 1 Asura Summon can be active a time.'),
 ('technobabble',
  'Technobabble',
  'Asura',
  'Unlock_technobabble',
  'Spell. Deals 30...40 damage to target and adjacent foes. Inflicts Dazed condition (3...5 seconds) on these foes if target was not a '
  'boss.'),
 ('deft_strike',
  'Deft Strike',
  'Vanguard',
  'Unlock_deft_strike',
  'Ranged Attack. Deals 18...30 damage. Inflicts Bleeding condition (18...30 seconds) if target foe has Cracked Armor.'),
 ('ebon_battle_standard_of_courage',
  'Ebon Battle Standard of Courage',
  'Vanguard',
  'Unlock_ebon_battle_standard_of_courage',
  'Ward Spell. (14...20 seconds.) Allies in this ward have +24 armor and +24 more armor against Charr. Spirits are unaffected.'),
 ('ebon_battle_standard_of_honor',
  'Ebon Battle Standard of Honor',
  'Vanguard',
  'Unlock_ebon_battle_standard_of_honor',
  'Ward Spell. (14...20 seconds.) Allies in this ward deal +8...15 damage and +7...10 more damage against Charr. Spirits are unaffected.'),
 ('ebon_battle_standard_of_wisdom',
  'Ebon Battle Standard of Wisdom',
  'Vanguard',
  'Unlock_ebon_battle_standard_of_wisdom',
  'Ward Spell. (14...20 seconds.) Spells that allies in this ward cast have a 44...60% chance to recharge 50% faster. Spirits are '
  'unaffected.'),
 ('ebon_escape',
  'Ebon Escape',
  'Vanguard',
  'Unlock_ebon_escape',
  'Spell. Heals you and target ally for 70...110. Initial effect: Shadow Step to this ally. Cannot self-target.'),
 ('ebon_vanguard_assassin_support',
  'Ebon Vanguard Assassin Support',
  'Vanguard',
  'Unlock_ebon_vanguard_assassin_support',
  'Spell. Summon a level 14...20 assassin that has Iron Palm, Fox Fangs, and Nine Tail Strike; it Shadow Steps to this foe. If this foe is '
  'a Charr, the assassin lives for 24...30 seconds.'),
 ('ebon_vanguard_sniper_support',
  'Ebon Vanguard Sniper Support',
  'Vanguard',
  'Unlock_ebon_vanguard_sniper_support',
  'Spell. Deals 54...90 piercing damage and inflicts Bleeding condition (5...25 seconds). 10% chance of big bonus damage; more if target '
  'is a Charr.'),
 ('signet_of_infection',
  'Signet of Infection',
  'Vanguard',
  'Unlock_signet_of_infection',
  'Signet. Inflicts Diseased condition 13...20 seconds if target foe is Bleeding.'),
 ('sneak_attack',
  'Sneak Attack',
  'Vanguard',
  'Unlock_sneak_attack',
  'Melee Attack. Inflicts Blindness (5...8 seconds). Counts as a lead attack.'),
 ('tryptophan_signet',
  'Tryptophan Signet',
  'Vanguard',
  'Unlock_tryptophan_signet',
  'Signet. (14...20 seconds.) Target and adjacent foes move and attack 23...40% slower.'),
 ('weakness_trap',
  'Weakness Trap',
  'Vanguard',
  'Unlock_weakness_trap',
  'Trap. (90 seconds.) Affects nearby foes. Deals 24...50 lightning damage. Inflicts Weakness (10...20 seconds). Knocks-down Charr.'),
 ('winds',
  'Winds',
  'Vanguard',
  'Unlock_winds',
  'Ebon Vanguard Ritual. Creates a spirit (54...90 seconds). Affects foes within range. 15% chance to miss with ranged attacks.'),
 ('dodge_this',
  '"Dodge This!"',
  'Norn',
  'Unlock_dodge_this',
  'Shout. (16...20 seconds.) Your next attack is unblockable and deals +14...20 damage.'),
 ('finish_him',
  '"Finish Him!"',
  'Norn',
  'Unlock_finish_him',
  'Shout. Deals 44...80 damage and inflicts Cracked Armor and Deep Wound (12...20 seconds). No effect unless target < 50% HP.'),
 ('i_am_unstoppable',
  '"I Am Unstoppable!"',
  'Norn',
  'Unlock_i_am_unstoppable',
  'Shout. (16...20 seconds.) You have +24 armor and cannot be knocked-down or Crippled.'),
 ('i_am_the_strongest',
  '"I Am the Strongest!"',
  'Norn',
  'Unlock_i_am_the_strongest',
  'Shout. Your next 5...8 attacks deal +14...20 damage.'),
 ('you_are_all_weaklings',
  '"You Are All Weaklings!"',
  'Norn',
  'Unlock_you_are_all_weaklings',
  'Shout. Inflicts Weakness (8...12 seconds). Also affects adjacent foes.'),
 ('you_move_like_a_dwarf',
  '"You Move Like a Dwarf!"',
  'Norn',
  'Unlock_you_move_like_a_dwarf',
  'Shout. Deals 44...80 damage, knock-down, and inflicts Crippled (8...15 seconds).'),
 ('a_touch_of_guile',
  'A Touch of Guile',
  'Norn',
  'Unlock_a_touch_of_guile',
  'Touch Hex Spell. Deals 44...80 damage. Target cannot attack (5...8 seconds) if it was knocked-down.'),
 ('club_of_a_thousand_bears',
  'Club of a Thousand Bears',
  'Norn',
  'Unlock_club_of_a_thousand_bears',
  'Melee Attack. Deals +6...9 damage for each adjacent foe (max 60). Causes knock-down if target is non-human.'),
 ('feel_no_pain',
  'Feel No Pain',
  'Norn',
  'Unlock_feel_no_pain',
  'Skill. (30 seconds.) +2...3 regen. +200...300 max HP if drunk when activated.'),
 ('raven_blessing',
  'Raven Blessing',
  'Norn',
  'Unlock_raven_blessing',
  'Elite Form. Raven aspect (60 seconds). Attributes set to 0; replaces skills; 80 armor, ~660-700 HP.'),
 ('ursan_blessing',
  'Ursan Blessing',
  'Norn',
  'Unlock_ursan_blessing',
  'Elite Form. Bear aspect (60 seconds). Attributes set to 0; replaces skills; 100 armor, ~750-800 HP.'),
 ('volfen_blessing',
  'Volfen Blessing',
  'Norn',
  'Unlock_volfen_blessing',
  'Elite Form. Wolf aspect (60 seconds). Attributes set to 0; replaces skills; 80 armor, ~660-700 HP.'),
 ('by_urals_hammer',
  '"By Ural\'s Hammer!"',
  'Deldrimor',
  'Unlock_by_ural_s_hammer',
  'Shout. (30 seconds.) Rez party in earshot with full HP/E. Party deals +25...33% dmg. They die when it ends (no DP).'),
 ('don_t_trip',
  '"Don\'t Trip!"',
  'Deldrimor',
  'Unlock_don_t_trip',
  'Shout. (3...5 seconds.) Prevents knock-down; affects party within earshot.'),
 ('alkars_alchemical_acid',
  "Alkar's Alchemical Acid",
  'Deldrimor',
  'Unlock_alkar_s_alchemical_acid',
  'Spell. Projectile: deals 40...50 damage. Deals extra vs Destroyers and inflicts Cracked Armor (14...20 seconds).'),
 ('black_powder_mine',
  'Black Powder Mine',
  'Deldrimor',
  'Unlock_black_powder_mine',
  'Trap. (90 seconds.) Deals 20...30 dmg. Inflicts Blindness and Bleeding (7...10 seconds).'),
 ('brawling_headbutt',
  'Brawling Headbutt',
  'Deldrimor',
  'Unlock_brawling_headbutt',
  'Touch Skill. Deals 45...70 damage; causes knock-down.'),
 ('breath_of_the_great_dwarf',
  'Breath of the Great Dwarf',
  'Deldrimor',
  'Unlock_breath_of_the_great_dwarf',
  'Spell. Removes burning and heals for 50...60 Health. Affects party members.'),
 ('drunken_master',
  'Drunken Master',
  'Deldrimor',
  'Unlock_drunken_master',
  'Stance. (72...90 seconds.) Move/attack faster; more if drunk.'),
 ('dwarven_stability',
  'Dwarven Stability',
  'Deldrimor',
  'Unlock_dwarven_stability',
  'Enchantment. (24...30 seconds.) Stances last longer. Cannot be knocked down if activated while drunk.'),
 ('ear_bite', 'Ear Bite', 'Deldrimor', 'Unlock_ear_bite', 'Touch. Deals 50...70 piercing dmg and inflicts Bleeding (15...25 seconds).'),
 ('great_dwarf_armor',
  'Great Dwarf Armor',
  'Deldrimor',
  'Unlock_great_dwarf_armor',
  'Enchantment. +24 armor and +60 max HP; extra vs Destroyers.'),
 ('great_dwarf_weapon',
  'Great Dwarf Weapon',
  'Deldrimor',
  'Unlock_great_dwarf_weapon',
  'Weapon Spell. +15...20 dmg and chance to KD. Cannot self-target.'),
 ('light_of_deldrimor',
  'Light of Deldrimor',
  'Deldrimor',
  'Unlock_light_of_deldrimor',
  'Spell. Holy dmg in area and pings hidden objects on compass.'),
 ('low_blow',
  'Low Blow',
  'Deldrimor',
  'Unlock_low_blow',
  'Touch. Deals 45...70 dmg. Extra dmg + Cracked Armor if target was knocked down.'),
 ('snow_storm',
  'Snow Storm',
  'Deldrimor',
  'Unlock_snow_storm',
  "Spell. Deals cold damage each second (5 seconds). Hits foes adjacent to target's initial location.")]

FACTIONS = ("Asura", "Vanguard", "Norn", "Deldrimor")

CHECKPOINT_LABEL_OVERRIDES = {
    "IAU:TAKE_ANYTHING_YOU_CAN_DO": "Take Anything You Can Do",
    "IAU:HUNT_AVARR_AND_WHITEOUT": "Hunt Avarr and Whiteout",
    "IAU:FRAGMENT_OF_ANTIQUITIES": "Start Fragment of Antiquities",
    "IAU:CLAIM_ANYTHING_YOU_CAN_DO": "Claim Anything You Can Do",
    "IAU:COLD_AS_ICE": "Cold as Ice solo fight",
    "IAU:CLAIM_FINAL_REWARD": "Claim final reward",
}

ROUTE_BUILDERS: dict[str, Callable[[], list[PlannerStep]]] = {
    'air_of_superiority': _steps_unlock_air_of_superiority,
    'asuran_scan': _steps_unlock_asuran_scan,
    'Mental_Block': _steps_unlock_mental_block,
    'pain_inverter': _steps_unlock_pain_inverter,
    'radiation_field': _steps_unlock_radiation_field,
    'smooth_criminal': _steps_unlock_smooth_criminal,
    'technobabble': _steps_unlock_technobabble,
    'summon_naga_shaman': _steps_unlock_summon_naga_shaman,
    'summon_ruby_djinn': _steps_unlock_summon_ruby_djinn,
    'summon_ice_imp': _steps_unlock_summon_ice_imp,
    'summon_mursaat': _steps_unlock_summon_mursaat,
    'deft_strike': _steps_unlock_deft_strike,
    'ebon_battle_standard_of_honor': _steps_unlock_ebon_battle_standard_of_honor,
    'ebon_escape': _steps_unlock_ebon_escape,
    'ebon_vanguard_assassin_support': _steps_unlock_ebon_vanguard_assassin_support,
    'winds': _steps_unlock_winds,
    'i_am_unstoppable': _steps_unlock_i_am_unstoppable,
    'you_move_like_a_dwarf': _steps_unlock_you_move_like_a_dwarf,
    'feel_no_pain': _steps_unlock_feel_no_pain,
    'dwarven_stability': _steps_unlock_dwarven_stability,
    'great_dwarf_weapon': _steps_unlock_great_dwarf_weapon,
    'alkars_alchemical_acid': _steps_unlock_alkar_alchemical_acid,
    'great_dwarf_armor': _steps_unlock_great_dwarf_armor,
    'light_of_deldrimor': _steps_unlock_light_of_deldrimor,
    'breath_of_the_great_dwarf' : steps_unlock_breath_of_the_great_dwarf,
    'by_urals_hammer' : _steps_unlock_by_urals_hammer,
    'mindbender' :_steps_unlock_mindbender
}

# ---------------------------------------------------------------------------
# Skill dependency graph
# ---------------------------------------------------------------------------

# Only dependencies whose prerequisite routes are already implemented are
# listed here. Missing learned prerequisites are automatically prepended.
#
# Verified quest chains:
#   Asura:
#     Smooth Criminal -> the four secondary Ciphers
#     four secondary Ciphers -> Pain Inverter -> Air of Superiority
#   Vanguard:
#     Winds -> Ebon Vanguard Assassin Support
#   Norn:
#     You Move Like a Dwarf! -> Anything You Can Do -> I Am Unstoppable!
#     (the IAU route already handles Anything You Can Do itself)
#   Deldrimor:
#     Great Dwarf Weapon / By Ural's Hammer! -> Great Dwarf Armor
SKILL_PREREQUISITES: dict[str, tuple[str, ...]] = {
    "Mental_Block": ("smooth_criminal",),
    "radiation_field": ("smooth_criminal",),
    "asuran_scan": ("smooth_criminal",),
    "technobabble": ("smooth_criminal",),

    "pain_inverter": (
        "Mental_Block",
        "radiation_field",
        "asuran_scan",
        "technobabble",
    ),
    "air_of_superiority": ("pain_inverter",),

    "ebon_vanguard_assassin_support": ("winds",),

    "i_am_unstoppable": ("you_move_like_a_dwarf",),

    "great_dwarf_armor": ("great_dwarf_weapon",),

    # The Destroyer Challenge is only available after Destructive Research.
    "alkars_alchemical_acid": ("light_of_deldrimor",),
}


# Requirements which are real quest prerequisites but do not yet have a
# complete automated route in ROUTE_BUILDERS.
#
# Destructive Research grants BOTH Light of Deldrimor and Breath of the Great
# Dwarf. Having either skill learned proves that prerequisite quest was
# completed on this character.
SKILL_EXTERNAL_REQUIREMENTS: dict[str, dict[str, object]] = {}


# Canonical names used by Skill.GetID(). Explicit aliases avoid punctuation
# differences between UI labels and Py4GW skill identifiers.
SKILL_API_NAMES: dict[str, str] = {
    "air_of_superiority": "Air_of_Superiority",
    "asuran_scan": "Asuran_Scan",
    "Mental_Block": "Mental_Block",
    "pain_inverter": "Pain_Inverter",
    "radiation_field": "Radiation_Field",
    "smooth_criminal": "Smooth_Criminal",
    "technobabble": "Technobabble",
    "summon_naga_shaman": "Summon_Naga_Shaman",
    "summon_ruby_djinn": "Summon_Ruby_Djinn",
    "summon_ice_imp": "Summon_Ice_Imp",
    "summon_mursaat": "Summon_Mursaat",
    "winds": "Winds",
    "ebon_escape": "Ebon_Escape",
    "ebon_vanguard_assassin_support": "Ebon_Vanguard_Assassin_Support",
    "you_move_like_a_dwarf": "You_Move_Like_a_Dwarf",
    "i_am_unstoppable": "I_Am_Unstoppable",
    "great_dwarf_weapon": "Great_Dwarf_Weapon",
    "great_dwarf_armor": "Great_Dwarf_Armor",
    "light_of_deldrimor": "Light_of_Deldrimor",
    "breath_of_the_great_dwarf": "Breath_of_the_Great_Dwarf",
    "alkars_alchemical_acid": "Alkars_Alchemical_Acid",
}


def _skill_entry_by_key(key: str):
    for entry in RAW_SKILLS:
        if entry[0] == key:
            return entry
    return None


def _skill_label(key: str) -> str:
    entry = _skill_entry_by_key(key)
    return str(entry[1]) if entry is not None else str(key)


def _skill_id_for_key(key: str) -> int:
    """Resolve a UI skill key to a Py4GW skill id."""
    candidates: list[str] = []

    explicit = SKILL_API_NAMES.get(key)
    if explicit:
        candidates.append(explicit)

    candidates.append(str(key))

    entry = _skill_entry_by_key(key)
    if entry is not None:
        label = str(entry[1])
        candidates.append(label)

        normalized = (
            label
            .replace('"', "")
            .replace("'", "")
            .replace("!", "")
            .replace("-", "_")
            .replace(" ", "_")
        )
        candidates.append(normalized)

    seen: set[str] = set()
    for candidate in candidates:
        candidate = str(candidate).strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)

        try:
            skill_id = int(GLOBAL_CACHE.Skill.GetID(candidate) or 0)
        except Exception:
            skill_id = 0

        if skill_id > 0:
            return skill_id

    return 0


def _skill_is_learned(key: str) -> bool:
    """Character-level check; account-wide unlocks do NOT satisfy prerequisites."""
    skill_id = _skill_id_for_key(key)
    if skill_id <= 0:
        return False

    try:
        return bool(GLOBAL_CACHE.SkillBar.IsSkillLearnt(skill_id))
    except Exception:
        return False


def _external_requirement_block_reason(key: str) -> str | None:
    requirement = SKILL_EXTERNAL_REQUIREMENTS.get(key)
    if requirement is None:
        return None

    any_of = tuple(requirement.get("any_of", ()))
    if any(_skill_is_learned(str(required_key)) for required_key in any_of):
        return None

    return str(requirement.get("message", "A prerequisite quest is still missing."))


def _skill_block_reason(key: str, _visited: set[str] | None = None) -> str | None:
    """
    Return a reason only when a required prerequisite cannot currently be
    automated. Automated missing prerequisite skills do NOT block the button.
    """
    visited = set() if _visited is None else set(_visited)
    if key in visited:
        return f"Dependency loop detected for {_skill_label(key)}."
    visited.add(key)

    external_reason = _external_requirement_block_reason(key)
    if external_reason:
        return external_reason

    for prerequisite in SKILL_PREREQUISITES.get(key, ()):
        if _skill_is_learned(prerequisite):
            continue

        if prerequisite not in ROUTE_BUILDERS:
            return (
                f"Requires {_skill_label(prerequisite)}, "
                "but that prerequisite route is not automated yet."
            )

        nested_reason = _skill_block_reason(prerequisite, visited)
        if nested_reason:
            return nested_reason

    return None


def _missing_automated_prerequisite_keys(key: str) -> list[str]:
    """Return missing automated prerequisites in actual execution order."""
    result: list[str] = []
    scheduled: set[str] = set()
    visiting: set[str] = set()

    def _visit(current_key: str) -> None:
        if current_key in visiting:
            return

        visiting.add(current_key)
        try:
            for prerequisite in SKILL_PREREQUISITES.get(current_key, ()):
                if _skill_is_learned(prerequisite):
                    continue
                if prerequisite not in ROUTE_BUILDERS:
                    continue

                _visit(prerequisite)

                if prerequisite not in scheduled and not _skill_is_learned(prerequisite):
                    result.append(prerequisite)
                    scheduled.add(prerequisite)
        finally:
            visiting.discard(current_key)

    _visit(key)
    return result


def _base_route_steps_for_key(key: str) -> list[PlannerStep]:
    """Return only the route belonging to key, with no automatic prerequisites."""
    builder = ROUTE_BUILDERS.get(key)
    if builder is not None:
        return builder()

    entry = _skill_entry_by_key(key)
    label = entry[1] if entry is not None else key
    return [(
        f"{label} - TODO",
        lambda label=label: BT.LogMessage(
            message=f"{label}: route is not implemented in the legacy source.",
            module_name=MODULE_NAME,
        ),
    )]


def _planned_route_keys(key: str) -> list[str]:
    """
    Build the complete prerequisite chain for a normal skill-button start.

    Already learned prerequisite skills are skipped. The requested skill itself
    is always appended so the button keeps its original behavior.
    """
    prerequisites = _missing_automated_prerequisite_keys(key)
    return [*prerequisites, key]


def _planned_route_steps_for_key(key: str) -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    for route_key in _planned_route_keys(key):
        steps.extend(_base_route_steps_for_key(route_key))
    return steps


def _route_checkpoints_for_key(key: str) -> list[tuple[str, str | None]]:
    # Route Controls are intentionally the raw selected-skill route only.
    # A manual checkpoint jump remains a debugging/advanced override.
    steps = _base_route_steps_for_key(key)
    result: list[tuple[str, str | None]] = [("0. Start entire route", None)]
    for index, (step_name, _factory) in enumerate(steps, start=1):
        display_name = CHECKPOINT_LABEL_OVERRIDES.get(step_name, step_name)
        result.append((f"{index}. {display_name}", step_name))
    return result


def _start_route(key: str, start_from: str | None = None) -> None:
    tree = ensure_botting_tree()

    # Normal starts enforce real prerequisite availability.
    # Explicit checkpoint jumps remain an advanced/manual override.
    if start_from is None:
        blocked_reason = _skill_block_reason(key)
        if blocked_reason:
            PySystem.Console.Log(
                MODULE_NAME,
                f"{_skill_label(key)} locked: {blocked_reason}",
                PySystem.Console.MessageType.Warning,
            )
            return
        steps = _planned_route_steps_for_key(key)
    else:
        steps = _base_route_steps_for_key(key)

    if not steps:
        return

    if tree.IsStarted():
        tree.Stop()

    # A manual route switch must never leave the temporary Polymock HeroAI
    # override active from the previous planner.
    if _polymock_runtime_active:
        _set_polymock_runtime(None, False)

    label = _skill_label(key)
    prerequisite_keys = (
        _missing_automated_prerequisite_keys(key)
        if start_from is None
        else []
    )

    if prerequisite_keys:
        chain = " -> ".join(
            [_skill_label(prerequisite) for prerequisite in prerequisite_keys]
            + [label]
        )
        PySystem.Console.Log(
            MODULE_NAME,
            f"Auto prerequisite chain: {chain}",
            PySystem.Console.MessageType.Info,
        )

    tree.SetCurrentNamedPlannerSteps(
        steps,
        start_from=start_from,
        name=f"Skills Unlocker - {label}",
        auto_start=True,
        reset=False,
        repeat=False,
    )


def _push_unlocked_skill_style() -> None:
    """Give learned skills a persistent blue frame/background around the icon."""

    PyImGui.push_style_color(
        PyImGui.ImGuiCol.Button,
        (0.05, 0.65, 0.85, 0.88),
    )

    PyImGui.push_style_color(
        PyImGui.ImGuiCol.ButtonHovered,
        (0.10, 0.80, 1.00, 0.98),
    )

    PyImGui.push_style_color(
        PyImGui.ImGuiCol.ButtonActive,
        (0.03, 0.52, 0.72, 1.00),
    )


def _is_item_hovered_including_disabled() -> bool:
    """Return hover state even for items inside begin_disabled()."""
    try:
        hovered_flags = getattr(PyImGui, "HoveredFlags", None)
        allow_when_disabled = (
            getattr(hovered_flags, "AllowWhenDisabled", None)
            if hovered_flags is not None
            else None
        )
        if allow_when_disabled is not None:
            return bool(PyImGui.is_item_hovered(allow_when_disabled))
    except Exception:
        pass

    # Current Dear ImGui value for ImGuiHoveredFlags_AllowWhenDisabled.
    # Kept behind a try so older bindings cannot break the UI.
    try:
        return bool(PyImGui.is_item_hovered(1024))
    except Exception:
        pass

    try:
        return bool(PyImGui.is_item_hovered())
    except Exception:
        return False


def _draw_skill_grid(faction: str) -> None:
    entries = [entry for entry in RAW_SKILLS if entry[2] == faction]
    if not entries:
        PyImGui.text("No Skill")
        return

    icon_size = 42
    cols = 5
    c = 0

    for key, label, _fac, fn_name, desc in entries:
        icon_path = _skill_icon_path(key)
        has_icon = icon_path is not None
        implemented = key in ROUTE_BUILDERS

        # Character-level learned state.
        learned = _skill_is_learned(key)

        # 1) Not implemented at all -> always greyed/disabled.
        # 2) Implemented but blocked by a non-automated prerequisite -> greyed/disabled.
        missing_route_reason = (
            "No unlock function exists for this skill yet."
            if not implemented
            else None
        )

        blocked_reason = (
            _skill_block_reason(key)
            if implemented and not learned
            else None
        )

        lock_reason = missing_route_reason or blocked_reason
        locked = bool(lock_reason)

        # Learned = green button/frame around the existing skill icon.
        if learned:
            _push_unlocked_skill_style()

        # Locked = standard ImGui disabled/greyed appearance.
        if locked:
            PyImGui.begin_disabled(True)

        if icon_path is not None:
            clicked = ImGui.ImageButton(
                f"##{key}",
                icon_path,
                icon_size,
                icon_size,
            )
        else:
            button_label = label if implemented else f"{label} [TODO]"
            clicked = PyImGui.button(button_label, 260, 40)

        if locked:
            PyImGui.end_disabled()

        if learned:
            PyImGui.pop_style_color(3)

        if clicked and not locked:
            _start_route(key)

        if _is_item_hovered_including_disabled():
            PyImGui.begin_tooltip()
            PyImGui.text(label)

            if learned:
                PyImGui.push_style_color(
                    PyImGui.ImGuiCol.Text,
                    (0.35, 1.00, 0.45, 1.00),
                )
                PyImGui.text("Unlocked on this character")
                PyImGui.pop_style_color(1)

            PyImGui.separator()
            PyImGui.text_wrapped(fn_name)
            PyImGui.separator()
            PyImGui.text_wrapped(desc)

            if locked:
                PyImGui.separator()
                PyImGui.text("Prerequisite:" if blocked_reason else "Status:")
                PyImGui.text_wrapped(str(lock_reason))
            elif not learned:
                missing_prerequisites = _missing_automated_prerequisite_keys(key)
                if missing_prerequisites:
                    PyImGui.separator()
                    chain = " -> ".join(
                        [_skill_label(prerequisite) for prerequisite in missing_prerequisites]
                        + [label]
                    )
                    PyImGui.text_wrapped(
                        f"Automatic prerequisite chain: {chain}"
                    )

            PyImGui.end_tooltip()

        if has_icon:
            c += 1
            if c % cols != 0:
                PyImGui.same_line(0.0, -1.0)

def draw_portal_ui() -> None:
    global _route_skill_index, _route_step_index, _route_previous_skill_index, _show_route_controls

    if PyImGui.button("Stop current route##SU_BT_Stop"):
        ensure_botting_tree().Stop()

    PyImGui.same_line(0.0, -1.0)
    toggle_label = "Hide Route Controls" if _show_route_controls else "Show Route Controls"
    if PyImGui.button(f"{toggle_label}##SU_BT_ToggleRouteControls"):
        _show_route_controls = not _show_route_controls

    PyImGui.same_line(0.0, -1.0)
    draw_support_button(unique_id="SkyKoFiSkillUnlocker")

    if _show_route_controls:
        current_step = str(ensure_botting_tree().GetBlackboardValue("current_step_name", "") or "")
        if current_step:
            PyImGui.text_wrapped(f"Current step: {current_step}")

        PyImGui.separator()
        PyImGui.text("Route Controls:")

        route_entries = [entry for entry in RAW_SKILLS if entry[0] in ROUTE_BUILDERS]
        if route_entries:
            route_labels = [f"[{entry[2]}] {entry[1]}" for entry in route_entries]
            _route_skill_index = max(0, min(_route_skill_index, len(route_entries) - 1))
            _route_skill_index = PyImGui.combo("Route##SU_BT_Route", _route_skill_index, route_labels)
            if _route_skill_index != _route_previous_skill_index:
                _route_step_index = 0
                _route_previous_skill_index = _route_skill_index

            key = route_entries[_route_skill_index][0]
            checkpoints = _route_checkpoints_for_key(key)
            checkpoint_labels = [label for label, _step_name in checkpoints]
            _route_step_index = max(0, min(_route_step_index, len(checkpoints) - 1))
            _route_step_index = PyImGui.combo(
                "Checkpoint##SU_BT_Checkpoint",
                _route_step_index,
                checkpoint_labels,
            )
            if PyImGui.button("Start / jump to checkpoint##SU_BT_JumpCheckpoint"):
                _label, checkpoint_name = checkpoints[_route_step_index]
                _start_route(key, start_from=checkpoint_name)
            if _route_step_index > 0:
                PyImGui.text_wrapped(
                    "Jumping ahead assumes all earlier quest objectives are already complete."
                )

    if _show_route_controls:
        PyImGui.separator()

    if PyImGui.begin_tab_bar("SU_BT_Factions"):
        for faction in FACTIONS:
            if PyImGui.begin_tab_item(faction):
                _draw_skill_grid(faction)
                PyImGui.end_tab_item()
        PyImGui.end_tab_bar()


# ---------------------------------------------------------------------------
# BottingTree lifecycle / compact UI
# ---------------------------------------------------------------------------


def _install_compact_ui(tree: BottingTree) -> None:
    """Use BottingTree's native window lifecycle with a smaller tab set."""
    from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

    ui = tree.UI

    def _draw_compact_managed_window() -> None:
        if not ui._ensure_window_paths():
            return

        p_open = (
            ui._floating_button.visible
            if ui._floating_button is not None
            else Settings(
                ui._main_ini_name,
                "account",
            ).get_bool(
                "Configuration",
                "show_main_window",
                True,
            )
        )

        expanded, open_ = ImGui.begin_with_close(
            tree.bot_name,
            p_open,
            PyImGui.WindowFlags(PyImGui.WindowFlags.AlwaysAutoResize),
        )

        if ui._floating_button is not None:
            ui._floating_button.sync_begin_with_close(open_)

        if expanded:
            if PyImGui.begin_tab_bar(tree.bot_name + "_compact_tabs"):
                if PyImGui.begin_tab_item("Main"):
                    draw_portal_ui()
                    PyImGui.end_tab_item()

                if PyImGui.begin_tab_item("Settings"):
                    ui._draw_settings_child()
                    PyImGui.end_tab_item()

                if PyImGui.begin_tab_item("Debug"):
                    ui.draw_debug_window()
                    PyImGui.end_tab_item()

                PyImGui.end_tab_bar()

        ImGui.end()

    # draw_window() will still handle the floating button, saved visibility,
    # and DrawMovePathIfEnabled(). Only the contents of the managed window
    # are replaced for this script.
    ui._draw_managed_window = _draw_compact_managed_window


def ensure_botting_tree() -> BottingTree:
    global botting_tree
    if botting_tree is None:
        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=None,
            repeat=False,
            auto_start=False,
            pause_on_combat=True,
            multi_account=True,
            auto_loot=True,
            auto_resurrection_scroll=False,
            isolation_enabled=False,
            configure_fn=_configure_botting_tree,
        )

        _install_compact_ui(botting_tree)

    return botting_tree


def main() -> None:
    global initialized
    tree = ensure_botting_tree()
    if not initialized:
        initialized = True

    tree.tick()

    # The custom Polymock engine is dormant unless a Polymock arena step has
    # explicitly scoped it on and disabled HeroAI for that match.
    _tick_polymock_combat()
    _restore_polymock_runtime_if_idle(tree)

    # Keep the native BottingTree draw lifecycle. The managed-window renderer
    # itself has been replaced by _install_compact_ui().
    tree.UI.draw_window(
        icon_path=TEXTURE,
        main_child_dimensions=(300, 260),
    )


if __name__ == "__main__":
    main()
