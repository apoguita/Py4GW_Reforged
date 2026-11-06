DiessaLowlands = [
    {
        "path": [
    (-20296,14688),
    (-18526,14753),
    (-17165,11540),
    (-14121,12424),
    (-13290,7335),
    (-14121,12424),
    (-9471,14739),
    (-4119,12964),
    (-7815,11751),
    (-12062,10422),
    (-11884,8833),
    (-6721,6493),
        ],
    },
    {
        # ROUTE-20260928-161040-467 ("DL: Detour 1").
        # Replaces the obstacle-prone direct approach to (-9849, 5349).
        "continuous_path": [
            (-8154.76, 5986.55),
            (-8652.32, 5903.67),
            (-9068.21, 5619.17),
            (-9424.5, 5468.6),
        ],
    },
    {
        "path": [
    (-9849,5349),
    (-11770,6007),
    (-9595,5400),
    (-6721,6493),
    (-6598,10696),
    (-6721,6493),
    (-7421,3355),
    (-4637,4171),
    (381,7729),
    (2415,9770),
    (5274,8243),
    (6863,10426),
    (8984,15766),
    (3726,14488),
    (8984,15766),
    (10742,15445),
    (10516,14744),
    (11202,15342),
    (14308,15521),
    (14449,12654),
    (9936,11541),
    (7526,9111),
    (7091,7527),
    (7797,4755),
    (9449,3227),
    (10073,2947),
    (9947,773),
    (13410,-952),
    (12992,-3384),
    (13996,1324),
    (14673,5243),
    (19299,5940),
    (22857,4443),
    (17976,6597),
    (15184,7566),
    (8717,7327),
    (5504,9646),
    (723,8076),
    (-1718,3774),
    (-5510,1030),
    (-3467,-2224),
    (-4030,-3247),
    (-649,-2185),
    (-5835,-5877),
    (-649,-2185),
    (-1386,589),
    (2316,2150),
    (2853,867),
    (6514,1048),
    (8840,-4058),
    (9238,-7447),
    (9690,-7831),
    (10828,-10741),
    (11546,-10190),
    (10177,-8109),
    (14517,-6115),
    (18276,-6046),
    (22121,-7474),
    (22721,-7921),
    (21979,-8612),
    (21982,-11599),
    (19543,-12982),
    (16172,-10242),
    (13003,-11708),
    (14384,-12971),
    (12117,-13427),
    (11657,-14108),
    (10415,-14069),
    (9686,-14026),
    (10392,-15363),
    (9215,-11545),
    (6960,-13619),
    (7632,-15429),
    (3012,-13708),
    (1205,-11994),
    (1977,-9505),
    (1660,-11367),
    (375,-9513),
    (-874,-9269),
    (-969,-10403),
    (-907,-9256),
    (372,-9381),
    (562,-6169),
    (-1218,-5715),
    (4,-6623),
    (-946,-7541),
        ],
    },
    {
        # LOC-20261005-165251-855 ("DL New Bridge Start") to
        # LOC-20261005-165238-466 ("DL New Bridge End"). The bridge deck
        # overlaps traversable ground in XY, so Gearward can select the lower
        # plane. Cross directly between the two deck endpoints without
        # autopathing or intermediate waypoints.
        "literal_path": [
            (-1554.53, -8095.58),
            (-3974.73, -10649.39),
        ],
    },
    {
        # Sweep the far side after the outbound literal crossing. Do not
        # restore (-5564, -10602): runtime movement evidence showed its
        # combat-resume autopath selecting the lower plane beneath the bridge.
        # These are the original far-side exploration points that follow the
        # unambiguous southern anchor. The next literal path returns directly
        # to the captured bridge end before crossing back.
        "path": [
    (-3743,-12348),
    (-4465,-11283),
    (-5140,-11862),
    (-5518,-12196),
    (-5168,-11824),
    (-4608,-11235),
        ],
    },
    {
        # Return across the same bridge using the exact captured deck
        # endpoints in reverse after the restored far-side exploration sweep.
        # Starting at the captured bridge end replaces the old ambiguous
        # bridge-adjacent autopath target (-4080, -10665).
        "literal_path": [
            (-3974.73, -10649.39),
            (-1554.53, -8095.58),
        ],
    },
    {
        "path": [
    # The reverse literal crossing already returns to the bridge start.
    # Skip the old bridge-adjacent autopath point (-926, -7547), whose XY
    # can resolve onto the overlapping lower plane, and hand directly to the
    # first unambiguous continuation point.
    (49,-6636),
    (-3086,-5833),
    (-4748,-6263),
    (-5078,-8220),
    (-7387,-9441),
    (-10436,-7893),
    (-10952,-2549),
        ],
    },
    {
        # ROUTE-20261005-170011-879 ("DL New Detour 1"). Inserted between
        # the existing route anchors to move around the tree without replacing
        # the sweep that follows. The duplicated finish sample is omitted.
        "continuous_path": [
            (-10895.51, -2635.5),
            (-11111.68, -2177.75),
            (-11613.83, -2156.07),
            (-11884.95, -2696.36),
            (-11971.09, -3038.46),
        ],
    },
    {
        "path": [
    (-11594,-5076),
    (-10704,-654),
    (-8724,1194),
    (-12003,2853),
    (-15387,5000),
    (-16970,7484),
    (-20811,6247),
    (-21623,7860),
    (-20785,4566),
    (-20839,6443),
    (-16351,3466),
    (-16654,3056),
    (-17255,1909),
    (-14099,126),
    (-15058,-3831),
    (-13613,-6649),
    # Split the former direct leg to (-11355, -13208) around the blocking
    # tree. The first point is the observed safe end of the preceding state;
    # the second is the user-provided avoidance waypoint.
    (-11900.66,-11450.16),
    (-11480.64,-11684.6),
    (-11355,-13208),
    (-12101,-14362),
    (-15051,-12087),
        ],
    },
    {
        # ROUTE-20260928-170830-103 ("DL: Detour 2"), outbound.
        "continuous_path": [
            (-16505.6, -11395.24),
            (-16979.5, -11214.91),
            (-16951.06, -11688.12),
        ],
    },
    {
        "path": [
    (-16718,-13141),
    (-21415,-15163),
    (-16851,-13219),
        ],
    },
    {
        # The same obstacle-prone corridor is traversed in reverse after the
        # western sweep, so preserve the capture in reverse order here.
        "continuous_path": [
            (-16951.06, -11688.12),
            (-16979.5, -11214.91),
            (-16505.6, -11395.24),
        ],
    },
    {
        "path": [
    (-15683,-9290),
    (-15618,-7314),
    (-16636,-10085),
    (-17011,-12736),
    (-18893,-10169),
    # User-provided rubble avoidance between installed states 195 and 196.
    (-17033.37,-10827.06),
    (-16892.25,-12053.03),
    (-19030,-9687),
    (-19030,-8796),
    (-19264,-8224),
    (-22397,-7208),
    (-19584,-6681),
    (-19614,-5775),
    (-19577,-5056),
    (-19905,-4869),
    (-21049,-4735),
    (-20808,-4163),
    (-19923,-4221),
    (-20710,-3629),
    (-20710,-2709),
    (-17794,-3038),
    (-19195,-738),
    (-19961,1863),
    (-16989,1528),
    (-16992,-553),
        ],
    },
]

DiessaLowlands_outpost_path = [
    (9342, 4942), (9240, 3985)
]
DiessaLowlands_transit_path = [
    (8304,-458),
    (10540,-4383),
    (10274,-11684),
    (9741,-16900),
    (10615,-17054),
    (11056,-17139),
]

DiessaLowlands_transit_path2 = [
    (-5680,1631),
    (-2243,2158),
    (-942,3489),
    (-942,5161),
    (1658,5873),
    (2432,7266),
    (6086,5099),
    (5900,1043),
    (3114,-3013),
    (7324,-4933),
    (7382,-6759),
    (7399,-7005),
]

DiessaLowlands_ids = {
    "outpost_id": 134,
    "map_id": 13,
    "transit_id": 99,
    "transit_id2": 103
}
