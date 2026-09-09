from __future__ import annotations

from collections.abc import Callable, Sequence
import os

import PyImGui
import PySystem

from Py4GWCoreLib import Agent, GLOBAL_CACHE, ImGui, Player
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.native_src.internals.types import Vec2f
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Sources.ApoSource.ApoBottingLib import wrappers as BT


BOT_NAME = "Skills Unlocker BT"
MODULE_NAME = BOT_NAME

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
TEXTURE = os.path.join(MODULE_DIR, "skills_unlocker.png")
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
        looting_enabled=False,
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
# Converted legacy routes
# ---------------------------------------------------------------------------

def _steps_unlock_previous_skills() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Smooth Criminal - 001 Travel', lambda: BT.Travel(target_map_id=641, log=True)))
    steps.append(('Smooth Criminal - 002 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=641, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Smooth Criminal - 003 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837c01, log=True)))
    steps.append(('Smooth Criminal - 004 Move', lambda: BT.Move(Vec2f(18781, -10477), log=False)))
    steps.append(('Smooth Criminal - 005 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Alcazia Tangle', timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Smooth Criminal - 006 Move', lambda: BT.Move(Vec2f(17024, -600), log=False)))
    steps.append(('Smooth Criminal - 007 Move', lambda: BT.Move(Vec2f(18237, 6691), log=False)))
    steps.append(('Smooth Criminal - 008 Move', lambda: BT.Move(Vec2f(15518, 8375), log=False)))
    steps.append(('Smooth Criminal - 009 Move', lambda: BT.Move(Vec2f(13200, 15000), log=False)))
    steps.append(('Smooth Criminal - 010 Wait', lambda: BT.Wait(3000)))
    steps.append(('Smooth Criminal - 011 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Smooth Criminal - 012 Move', lambda: BT.Move(Vec2f(19516, 4686), log=False)))
    steps.append(('Smooth Criminal - 013 Move', lambda: BT.Move(Vec2f(12184, 370), log=False)))
    steps.append(('Smooth Criminal - 014 Move', lambda: BT.Move(Vec2f(4802, -4990), log=False)))
    steps.append(('Smooth Criminal - 015 Move', lambda: BT.Move(Vec2f(-8760, -3378), log=False)))
    steps.append(('Smooth Criminal - 016 Move', lambda: BT.Move(Vec2f(-5555, -2108), log=False)))
    steps.append(('Smooth Criminal - 017 Move', lambda: BT.Move(Vec2f(-6678, 6477), log=False)))
    steps.append(('Smooth Criminal - 018 Wait', lambda: BT.Wait(3000)))
    steps.append(('Smooth Criminal - 019 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Smooth Criminal - 020 Move', lambda: BT.Move(Vec2f(-8860, -3178), log=False)))
    steps.append(('Smooth Criminal - 021 Move', lambda: BT.Move(Vec2f(-11202, 758), log=False)))
    steps.append(('Smooth Criminal - 022 Wait', lambda: BT.Wait(3000)))
    steps.append(('Smooth Criminal - 023 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Smooth Criminal - 024 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Smooth Criminal - 025 Wait', lambda: BT.Wait(3000)))
    steps.append(('Smooth Criminal - 026 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=641, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Smooth Criminal - 027 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837c07, log=True)))
    steps.append(('Smooth Criminal - 028 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    steps.append(('Mental Block - 029 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837701, log=True)))
    steps.append(('Mental Block - 030 Travel', lambda: BT.Travel(target_map_id=639, log=True)))
    steps.append(('Mental Block - 031 Move', lambda: BT.Move(Vec2f(-22999, 6530), log=False)))
    steps.append(('Mental Block - 032 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=566, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Mental Block - 033 Move', lambda: BT.Move(Vec2f(-9761, -8000), log=False)))
    steps.append(('Mental Block - 034 Move', lambda: BT.Move(Vec2f(7622, -9747), log=False)))
    steps.append(('Mental Block - 035 Move', lambda: BT.Move(Vec2f(11690, -6215), log=False)))
    steps.append(('Mental Block - 036 Move', lambda: BT.Move(Vec2f(15918, -2667), log=False)))
    steps.append(('Mental Block - 037 Wait', lambda: BT.Wait(3000)))
    steps.append(('Mental Block - 038 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Mental Block - 039 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Mental Block - 040 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=639, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Mental Block - 041 Travel', lambda: BT.Travel(target_map_id=641, log=True)))
    steps.append(('Mental Block - 042 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837707, log=True)))
    steps.append(('Mental Block - 043 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    steps.append(('Radiation Field - 044 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Radiation Field - 045 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837801, log=True)))
    steps.append(('Radiation Field - 046 Travel', lambda: BT.Travel(target_map_name='Rata Sum', log=True)))
    steps.append(('Radiation Field - 047 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(20340, 16899), target_map_name='Riven Earth', timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.extend(_movement_point_steps('Radiation Field - 048 Route', PREVIOUS_SKILLS_PATH_01))
    steps.append(('Radiation Field - 049 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Radiation Field - 050 Move', lambda: BT.Move(Vec2f(-5226.4, -2772.8), log=False)))
    steps.append(('Radiation Field - 051 Wait', lambda: BT.Wait(10000)))
    steps.append(('Radiation Field - 052 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Radiation Field - 053 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Radiation Field - 054 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Rata Sum', timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Radiation Field - 055 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Radiation Field - 056 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837807, log=True)))
    steps.append(('Radiation Field - 057 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    steps.append(('Asuran Scan - 058 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Asuran Scan - 059 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837901, log=True)))
    steps.append(('Asuran Scan - 060 Travel', lambda: BT.Travel(target_map_name="Gadd's Encampment", log=True)))
    steps.append(('Asuran Scan - 061 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-9690, -19524), target_map_name='Sparkfly Swamp', timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.extend(_movement_point_steps('Asuran Scan - 062 Route', PREVIOUS_SKILLS_PATH_02))
    steps.append(('Asuran Scan - 063 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Asuran Scan - 064 Wait', lambda: BT.Wait(10000)))
    steps.append(('Asuran Scan - 065 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Asuran Scan - 066 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name="Gadd's Encampment", timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Asuran Scan - 067 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Asuran Scan - 068 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837907, log=True)))
    steps.append(('Asuran Scan - 069 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    steps.append(('Technobabble - 070 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Technobabble - 071 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837b01, log=True)))
    steps.append(('Technobabble - 072 Travel', lambda: BT.Travel(target_map_name='Rata Sum', log=True)))
    steps.append(('Technobabble - 073 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-6062, -2688), target_map_name='Magus Stones', timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.extend(_movement_point_steps('Technobabble - 074 Route', PREVIOUS_SKILLS_PATH1_03))
    steps.append(('Technobabble - 075 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.extend(_movement_point_steps('Technobabble - 076 Route', PREVIOUS_SKILLS_PATH2_04))
    steps.append(('Technobabble - 077 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.extend(_movement_point_steps('Technobabble - 078 Route', PREVIOUS_SKILLS_PATH3_05))
    steps.append(('Technobabble - 079 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Technobabble - 080 Wait', lambda: BT.Wait(10000)))
    steps.append(('Technobabble - 081 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Technobabble - 082 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Rata Sum', timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Technobabble - 083 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Technobabble - 084 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837b07, log=True)))
    steps.append(('Technobabble - 085 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    steps.append(('Pain Inverter - 086 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Pain Inverter - 087 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837a01, log=True)))
    steps.append(('Pain Inverter - 088 Travel', lambda: BT.Travel(target_map_name="Vlox's Falls", log=True)))
    steps.append(('Pain Inverter - 089 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(15505.38, 12460.59), target_map_name='Arbor Bay', timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.extend(_movement_point_steps('Pain Inverter - 090 Route', PREVIOUS_SKILLS_PATH_06))
    steps.append(('Pain Inverter - 091 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Pain Inverter - 092 Wait', lambda: BT.Wait(10000)))
    steps.append(('Pain Inverter - 093 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Pain Inverter - 094 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name="Vlox's Falls", timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Pain Inverter - 095 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Pain Inverter - 096 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837a07, log=True)))
    steps.append(('Pain Inverter - 097 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


def _steps_unlock_air_of_superiority() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.extend(_steps_unlock_previous_skills())
    steps.append(('Air of Superiority - 001 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Air of Superiority - 002 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837d01, log=True)))
    steps.append(('Air of Superiority - 003 Travel', lambda: BT.Travel(target_map_name='Olafstead', log=True)))
    steps.append(('Air of Superiority - 004 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(1440, 1147.0), target_map_name='Varajar Fells', timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.extend(_movement_point_steps('Air of Superiority - 005 Route', AIR_OF_SUPERIORITY_PATH_01))
    steps.append(('Air of Superiority - 006 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Air of Superiority - 007 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(22648.0, 1078.0), 0x837d07, log=True)))
    steps.append(('Air of Superiority - 008 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    steps.append(('Air of Superiority - 009 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Air of Superiority - 010 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Olafstead', timeout_ms=MAP_TIMEOUT_MS)))
    return steps


def _steps_unlock_asuran_scan() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Asuran Scan - 001 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Asuran Scan - 002 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837901, log=True)))
    steps.append(('Asuran Scan - 003 Travel', lambda: BT.Travel(target_map_name="Gadd's Encampment", log=True)))
    steps.append(('Asuran Scan - 004 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-9690, -19524), target_map_name='Sparkfly Swamp', timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.extend(_movement_point_steps('Asuran Scan - 005 Route', ASURAN_SCAN_PATH_01))
    steps.append(('Asuran Scan - 006 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Asuran Scan - 007 Wait', lambda: BT.Wait(10000)))
    steps.append(('Asuran Scan - 008 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Asuran Scan - 009 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name="Gadd's Encampment", timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Asuran Scan - 010 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Asuran Scan - 011 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837907, log=True)))
    steps.append(('Asuran Scan - 012 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
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
    steps.append(('Mental Block - 008 Move', lambda: BT.Move(Vec2f(-9761, -8000), log=False)))
    steps.append(('Mental Block - 009 Move', lambda: BT.Move(Vec2f(7833, -8293), log=False)))
    steps.append(('Mental Block - 010 Move', lambda: BT.Move(Vec2f(11690, -6215), log=False)))
    steps.append(('Mental Block - 011 Move', lambda: BT.Move(Vec2f(15918, -2667), log=False)))
    steps.append(('Mental Block - 012 Wait', lambda: BT.Wait(3000)))
    steps.append(('Mental Block - 013 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Mental Block - 014 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Mental Block - 015 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=639, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Mental Block - 016 Travel', lambda: BT.Travel(target_map_id=641, log=True)))
    steps.append(('Mental Block - 017 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=641, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Mental Block - 018 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837707, log=True)))
    return steps


def _steps_unlock_pain_inverter() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Pain Inverter - 001 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Pain Inverter - 002 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837a01, log=True)))
    steps.append(('Pain Inverter - 003 Travel', lambda: BT.Travel(target_map_name="Vlox's Falls", log=True)))
    steps.append(('Pain Inverter - 004 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(15505.38, 12460.59), target_map_name='Arbor Bay', timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.extend(_movement_point_steps('Pain Inverter - 005 Route', PAIN_INVERTER_PATH_01))
    steps.append(('Pain Inverter - 006 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Pain Inverter - 007 Wait', lambda: BT.Wait(10000)))
    steps.append(('Pain Inverter - 008 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Pain Inverter - 009 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name="Vlox's Falls", timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Pain Inverter - 010 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Pain Inverter - 011 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837a07, log=True)))
    steps.append(('Pain Inverter - 012 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


def _steps_unlock_radiation_field() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Radiation Field - 001 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Radiation Field - 002 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837801, log=True)))
    steps.append(('Radiation Field - 003 Travel', lambda: BT.Travel(target_map_name='Rata Sum', log=True)))
    steps.append(('Radiation Field - 004 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(20340, 16899), target_map_name='Riven Earth', timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.extend(_movement_point_steps('Radiation Field - 005 Route', RADIATION_FIELD_PATH_01))
    steps.append(('Radiation Field - 006 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Radiation Field - 007 Move', lambda: BT.Move(Vec2f(-5226.4, -2772.8), log=False)))
    steps.append(('Radiation Field - 008 Wait', lambda: BT.Wait(10000)))
    steps.append(('Radiation Field - 009 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Radiation Field - 010 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Radiation Field - 011 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Rata Sum', timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Radiation Field - 012 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Radiation Field - 013 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837807, log=True)))
    steps.append(('Radiation Field - 014 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
    return steps


def _steps_unlock_smooth_criminal() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Smooth Criminal - 001 Travel', lambda: BT.Travel(target_map_id=641, log=True)))
    steps.append(('Smooth Criminal - 002 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=641, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Smooth Criminal - 003 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837c01, log=True)))
    steps.append(('Smooth Criminal - 004 Move', lambda: BT.Move(Vec2f(18781, -10477), log=False)))
    steps.append(('Smooth Criminal - 005 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Alcazia Tangle', timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Smooth Criminal - 006 Move', lambda: BT.Move(Vec2f(17024, -600), log=False)))
    steps.append(('Smooth Criminal - 007 Move', lambda: BT.Move(Vec2f(18237, 6691), log=False)))
    steps.append(('Smooth Criminal - 008 Move', lambda: BT.Move(Vec2f(15518, 8375), log=False)))
    steps.append(('Smooth Criminal - 009 Move', lambda: BT.Move(Vec2f(13200, 15000), log=False)))
    steps.append(('Smooth Criminal - 010 Wait', lambda: BT.Wait(3000)))
    steps.append(('Smooth Criminal - 011 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Smooth Criminal - 012 Move', lambda: BT.Move(Vec2f(19516, 4686), log=False)))
    steps.append(('Smooth Criminal - 013 Move', lambda: BT.Move(Vec2f(12184, 370), log=False)))
    steps.append(('Smooth Criminal - 014 Move', lambda: BT.Move(Vec2f(4802, -4990), log=False)))
    steps.append(('Smooth Criminal - 015 Move', lambda: BT.Move(Vec2f(-8760, -3378), log=False)))
    steps.append(('Smooth Criminal - 016 Move', lambda: BT.Move(Vec2f(-5555, -2108), log=False)))
    steps.append(('Smooth Criminal - 017 Move', lambda: BT.Move(Vec2f(-6678, 6477), log=False)))
    steps.append(('Smooth Criminal - 018 Wait', lambda: BT.Wait(3000)))
    steps.append(('Smooth Criminal - 019 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Smooth Criminal - 020 Move', lambda: BT.Move(Vec2f(-8860, -3178), log=False)))
    steps.append(('Smooth Criminal - 021 Move', lambda: BT.Move(Vec2f(-11202, 758), log=False)))
    steps.append(('Smooth Criminal - 022 Wait', lambda: BT.Wait(3000)))
    steps.append(('Smooth Criminal - 023 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Smooth Criminal - 024 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Smooth Criminal - 025 Wait', lambda: BT.Wait(3000)))
    steps.append(('Smooth Criminal - 026 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=641, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Smooth Criminal - 027 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837c07, log=True)))
    return steps


def _steps_unlock_technobabble() -> list[PlannerStep]:
    steps: list[PlannerStep] = []
    steps.append(('Technobabble - 001 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Technobabble - 002 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837b01, log=True)))
    steps.append(('Technobabble - 003 Travel', lambda: BT.Travel(target_map_name='Rata Sum', log=True)))
    steps.append(('Technobabble - 004 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-6062, -2688), target_map_name='Magus Stones', timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.extend(_movement_point_steps('Technobabble - 005 Route', TECHNOBABBLE_PATH1_01))
    steps.append(('Technobabble - 006 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.extend(_movement_point_steps('Technobabble - 007 Route', TECHNOBABBLE_PATH2_02))
    steps.append(('Technobabble - 008 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.extend(_movement_point_steps('Technobabble - 009 Route', TECHNOBABBLE_PATH3_03))
    steps.append(('Technobabble - 010 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Technobabble - 011 Wait', lambda: BT.Wait(10000)))
    steps.append(('Technobabble - 012 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Technobabble - 013 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Rata Sum', timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Technobabble - 014 Travel', lambda: BT.Travel(target_map_name='Tarnished Haven', log=True)))
    steps.append(('Technobabble - 015 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(25203, -10694), 0x837b07, log=True)))
    steps.append(('Technobabble - 016 Cancel Skill Reward Window', lambda: BT.CancelSkillRewardWindow()))
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
    steps.append(('I Am Unstoppable! - 002 Travel', lambda: BT.Travel(target_map_name='Sifhalla', log=True)))
    steps.append(('I Am Unstoppable! - 003 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=643, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('I Am Unstoppable! - 004 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(14380, 23874), 0x833e01, log=True)))
    steps.append(('IAU:HUNT_AVARR_AND_WHITEOUT', lambda: BT.Succeeder(name='IAU:HUNT_AVARR_AND_WHITEOUT')))
    steps.append(('I Am Unstoppable! - 006 Travel', lambda: BT.Travel(target_map_name='Sifhalla', log=True)))
    steps.append(('I Am Unstoppable! - 007 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=643, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('I Am Unstoppable! - 008 Move', lambda: BT.Move(Vec2f(14682, 22900), log=False)))
    steps.append(('I Am Unstoppable! - 009 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(17000, 22872), target_map_id=546, timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.append(('I Am Unstoppable! - 010 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=546, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('I Am Unstoppable! - 011 Move', lambda: BT.Move(Vec2f(-9431, -20124), log=False)))
    steps.append(('I Am Unstoppable! - 012 Move', lambda: BT.Move(Vec2f(-8441, -13685), log=False)))
    steps.append(('I Am Unstoppable! - 013 Move', lambda: BT.Move(Vec2f(-9743, -6744), log=False)))
    steps.append(('I Am Unstoppable! - 014 Move', lambda: BT.Move(Vec2f(-10672, 4815), log=False)))
    steps.append(('I Am Unstoppable! - 015 Move', lambda: BT.Move(Vec2f(-8464, 17239), log=False)))
    steps.append(('I Am Unstoppable! - 016 Move', lambda: BT.Move(Vec2f(-11700, 24101), log=False)))
    steps.append(('I Am Unstoppable! - 017 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('I Am Unstoppable! - 018 Move', lambda: BT.Move(Vec2f(-8464, 17239), log=False)))
    steps.append(('I Am Unstoppable! - 019 Move', lambda: BT.Move(Vec2f(-638, 17801), log=False)))
    steps.append(('I Am Unstoppable! - 020 Move', lambda: BT.Move(Vec2f(-933, 15368), log=False)))
    steps.append(('I Am Unstoppable! - 021 Wait', lambda: BT.Wait(6000)))
    steps.append(('I Am Unstoppable! - 022 Move', lambda: BT.Move(Vec2f(-1339, 22089), log=False)))
    steps.append(('I Am Unstoppable! - 023 Wait', lambda: BT.Wait(5000)))
    steps.append(('IAU:FRAGMENT_OF_ANTIQUITIES', lambda: BT.Succeeder(name='IAU:FRAGMENT_OF_ANTIQUITIES')))
    steps.append(('I Am Unstoppable! - 025 Travel', lambda: BT.Travel(target_map_name='Sifhalla', log=True)))
    steps.append(('I Am Unstoppable! - 026 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=643, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Fragment of Antiquities - 027 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(8832, 23870), target_map_id=513, timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.append(('Fragment of Antiquities - 028 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=513, timeout_ms=MAP_TIMEOUT_MS)))
    steps.extend(_movement_point_steps('Fragment of Antiquities - 029 Route', DRAKKAR_TO_REMLOK_ROUTE_XY[:-2]))
    steps.append(('Fragment of Antiquities - 030 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-10926, 24732), 0x832901, log=True)))
    steps.append(('Fragment of Antiquities - 031 Move', lambda: BT.Move(Vec2f(-11293.05, 24868.94), log=False)))
    steps.append(('Fragment of Antiquities - 032 Move', lambda: BT.Move(Vec2f(-11603.0, 24975.0), log=False)))
    steps.append(('Fragment of Antiquities - 033 Move', lambda: BT.Move(Vec2f(-11763.68, 25412.23), log=False)))
    steps.append(('Fragment of Antiquities - 034 Move', lambda: BT.Move(Vec2f(-11904.67, 25896.55), log=False)))
    steps.append(('Fragment of Antiquities - 035 Move', lambda: BT.Move(Vec2f(-12009.97, 26331.78), log=False)))
    steps.append(('Fragment of Antiquities - 036 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-12138, 26829), target_map_id=628, timeout_ms=MAP_TIMEOUT_MS, log=True)))
    steps.append(('Fragment of Antiquities - 037 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=628, timeout_ms=MAP_TIMEOUT_MS)))
    steps.extend(_movement_point_steps('Fragment of Antiquities - 038 Route', SEPULCHRE_PROOF_OF_STRENGTH_ROUTE_XY))
    steps.append(('Fragment of Antiquities - 039 Wait', lambda: BT.Wait(1500)))
    steps.extend(_movement_point_steps('Fragment of Antiquities - 040 Route', SEPULCHRE_LEVEL1_FRAGMENT_ROUTE_XY))
    steps.append(('Fragment of Antiquities - 041 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('IAU:CLAIM_ANYTHING_YOU_CAN_DO', lambda: BT.Succeeder(name='IAU:CLAIM_ANYTHING_YOU_CAN_DO')))
    steps.append(('Fragment of Antiquities - 043 Travel', lambda: BT.Travel(target_map_name='Sifhalla', log=True)))
    steps.append(('Fragment of Antiquities - 044 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=643, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Fragment of Antiquities - 045 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(14380, 23968), 0x833e07, log=True)))
    steps.append(('IAU:COLD_AS_ICE', lambda: BT.Succeeder(name='IAU:COLD_AS_ICE')))
    steps.append(('Fragment of Antiquities - 047 Travel', lambda: BT.Travel(target_map_name='Sifhalla', log=True)))
    steps.append(('Fragment of Antiquities - 048 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=643, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Fragment of Antiquities - 049 Spawn Bonus Items', lambda: BT.SpawnBonusItems(log=True)))
    steps.append(('Fragment of Antiquities - 050 Equip Item', lambda: BT.EquipItemByModelID(ModelID.Bonus_Nevermore_Flatbow.value, log=True)))
    steps.append(('Fragment of Antiquities - 051 Equip Item', lambda: BT.EquipItemByModelID(6515, log=True)))
    steps.append(('Fragment of Antiquities - 052 Equip Skill Bar', lambda: _iau_equip_skillbar()))
    steps.append(('Fragment of Antiquities - 053 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(14380, 23968), 0x834401, log=True)))
    steps.append(('Fragment of Antiquities - 054 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(14380, 23968), 0x85, log=True)))
    steps.append(('Fragment of Antiquities - 055 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=690, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('Fragment of Antiquities - 056 Wait', lambda: BT.Wait(5000)))
    steps.append(('Fragment of Antiquities - 057 Move', lambda: BT.Move(Vec2f(14553, 23043), log=False)))
    steps.append(('Fragment of Antiquities - 058 Wait', lambda: BT.Wait(2000)))
    steps.append(('Fragment of Antiquities - 059 Use Skill', lambda: BT.CastSkillID(skill_id=114, log=True)))
    steps.append(('Fragment of Antiquities - 060 Wait Until On Combat', lambda: BT.WaitUntilOnCombat(timeout_ms=120_000)))
    steps.append(('Fragment of Antiquities - 061 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)))
    steps.append(('Fragment of Antiquities - 062 Resign Party', lambda: BT.Resign(multi_account=True, log=True)))
    steps.append(('Fragment of Antiquities - 063 Wait', lambda: BT.Wait(20000)))
    steps.append(('Fragment of Antiquities - 064 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=643, timeout_ms=MAP_TIMEOUT_MS)))
    steps.append(('IAU:CLAIM_FINAL_REWARD', lambda: BT.Succeeder(name='IAU:CLAIM_FINAL_REWARD')))
    steps.append(('Fragment of Antiquities - 066 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(14380, 23968), 0x834407, log=True)))
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
    'deft_strike': _steps_unlock_deft_strike,
    'ebon_battle_standard_of_honor': _steps_unlock_ebon_battle_standard_of_honor,
    'ebon_vanguard_assassin_support': _steps_unlock_ebon_vanguard_assassin_support,
    'winds': _steps_unlock_winds,
    'i_am_unstoppable': _steps_unlock_i_am_unstoppable,
    'you_move_like_a_dwarf': _steps_unlock_you_move_like_a_dwarf,
    'feel_no_pain': _steps_unlock_feel_no_pain,
    'dwarven_stability': _steps_unlock_dwarven_stability,
}

def _skill_entry_by_key(key: str):
    for entry in RAW_SKILLS:
        if entry[0] == key:
            return entry
    return None


def _route_steps_for_key(key: str) -> list[PlannerStep]:
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


def _route_checkpoints_for_key(key: str) -> list[tuple[str, str | None]]:
    steps = _route_steps_for_key(key)
    result: list[tuple[str, str | None]] = [("0. Start entire route", None)]
    for index, (step_name, _factory) in enumerate(steps, start=1):
        display_name = CHECKPOINT_LABEL_OVERRIDES.get(step_name, step_name)
        result.append((f"{index}. {display_name}", step_name))
    return result


def _start_route(key: str, start_from: str | None = None) -> None:
    tree = ensure_botting_tree()
    steps = _route_steps_for_key(key)
    if not steps:
        return
    if tree.IsStarted():
        tree.Stop()
    entry = _skill_entry_by_key(key)
    label = entry[1] if entry is not None else key
    tree.SetCurrentNamedPlannerSteps(
        steps,
        start_from=start_from,
        name=f"Skills Unlocker - {label}",
        auto_start=True,
        reset=False,
        repeat=False,
    )


def _draw_skill_grid(faction: str) -> None:
    entries = [entry for entry in RAW_SKILLS if entry[2] == faction]
    if not entries:
        PyImGui.text("No Skill")
        return

    icon_size = 48
    cols = 4
    c = 0
    for key, label, _fac, fn_name, desc in entries:
        icon_path = _skill_icon_path(key)
        has_icon = icon_path is not None
        implemented = key in ROUTE_BUILDERS

        if icon_path is not None:
            clicked = ImGui.ImageButton(f"##{key}", icon_path, icon_size, icon_size)
        else:
            button_label = label if implemented else f"{label} [TODO]"
            clicked = PyImGui.button(button_label, 260, 40)

        if clicked:
            _start_route(key)

        if PyImGui.is_item_hovered():
            PyImGui.begin_tooltip()
            PyImGui.text(label)
            PyImGui.separator()
            PyImGui.text_wrapped(fn_name)
            PyImGui.separator()
            PyImGui.text_wrapped(desc)
            if not implemented:
                PyImGui.separator()
                PyImGui.text_wrapped("No active route exists for this skill in the legacy source.")
            PyImGui.end_tooltip()

        if has_icon:
            c += 1
            if c % cols != 0:
                PyImGui.same_line(0.0, -1.0)


def draw_portal_ui() -> None:
    global _route_skill_index, _route_step_index, _route_previous_skill_index

    if PyImGui.button("Stop current route##SU_BT_Stop"):
        ensure_botting_tree().Stop()

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

    PyImGui.separator()
    PyImGui.text("Select Skill:")
    PyImGui.separator()

    if PyImGui.begin_tab_bar("SU_BT_Factions"):
        for faction in FACTIONS:
            if PyImGui.begin_tab_item(faction):
                _draw_skill_grid(faction)
                PyImGui.end_tab_item()
        PyImGui.end_tab_bar()


# ---------------------------------------------------------------------------
# BottingTree lifecycle
# ---------------------------------------------------------------------------


def _draw_compact_main_child(
    _main_child_dimensions: tuple[int, int],
    _icon_path: str,
    _iconwidth: int,
) -> None:
    """Draw only the Skills Unlocker controls in the BottingTree Main tab."""
    draw_portal_ui()


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
            auto_loot=False,
            auto_resurrection_scroll=False,
            isolation_enabled=False,
            configure_fn=_configure_botting_tree,
        )

        # BottingTree currently has no public option to hide its standard Main
        # status block. Override that draw callback only for this script so the
        # skill selector is visible immediately, while Navigation/Settings/Help/
        # Debug remain provided by the normal BottingTree window.
        botting_tree.UI._draw_main_child = _draw_compact_main_child

    return botting_tree


def main() -> None:
    global initialized
    tree = ensure_botting_tree()
    if not initialized:
        initialized = True
    tree.tick()
    tree.UI.draw_window(
        icon_path=TEXTURE,
        main_child_dimensions=(360, 430),
    )


if __name__ == "__main__":
    main()
