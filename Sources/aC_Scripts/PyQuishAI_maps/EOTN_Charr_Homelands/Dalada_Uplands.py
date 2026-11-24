VANGUARD_PATROL_EFFECT_IDS = (
    2457, 2458, 2459, 2460, 2550, 2578, 2579, 2580, 2581, 2582,
)


def _vanguard_blessing(
    *, occurrence_key, interaction_mode, route_standoff_xy, target_xy,
    encoded_name, model_id, target_name, capture_ids=(),
):
    blessing = {
        "name": f"Dalada Uplands - {target_name} at {target_xy}",
        "occurrence_key": occurrence_key,
        "interaction_mode": interaction_mode,
        "buttons": 0,
        "route_standoff_xy": route_standoff_xy,
        "player_approach_xy": route_standoff_xy,
        "target_xy": target_xy,
        "encoded_name": encoded_name,
        "model_id": model_id,
        "target_name": target_name,
        "effect_ids": VANGUARD_PATROL_EFFECT_IDS,
    }
    if capture_ids:
        blessing["capture_ids"] = tuple(capture_ids)
    return blessing


_INITIAL_SWEEP = [
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
]

_SECOND_SWEEP = [
    (-1172.4, 95.6), (2474.3, 1913.7), (6476.9, 2343.3), (5489.0, -1545.9),
    (5552.4, -5596.4), (7189.7, -9305.8), (8261.67, -12055.48), (5228.1, -5784.1),
    (2164.1, -3177.7), (-1530.8, -4867.3), (156.3, -8499.8), (3819.1, -10133.5),
    (2167.7, -13796.2), (-1821.5, -14135.8), (-5747.9, -13218.7),
]

_THIRD_SWEEP = [
    (-5747.9, -13218.7), (-9790.9, -13258.0), (-11047.5, -9448.2), (-7777.1, -7032.2),
    (-4638.2, -4496.5), (-1131.0, -2524.7), (1852.3, 163.3), (5104.8, 2594.2),
    (8307.3, 5060.4), (7509.3, 8998.1), (10537.1, 11668.0), (8091.5, 8492.2),
    (11725.8, 6705.3), (7964.3, 8157.4), (4666.3, 10422.2),
]


Dalada_Uplands = [
    {
        "vanguard_blessing": _vanguard_blessing(
            occurrence_key="eotn.npc.ascalonian_refugee.dalada_uplands.-14971_11013",
            interaction_mode="first", route_standoff_xy=(-14991.40, 11131.25),
            target_xy=(-14971.0, 11013.0), encoded_name="\\x8102\\x0433\\xEC61\\x8B65\\x3147",
            model_id=2037, target_name="Ascalonian Refugee",
            capture_ids=("NPC-20260906-123122-771", "NPC-20260922-190658-984", "NPC-20260922-191454-618"),
        ),
        "path": _INITIAL_SWEEP[:8],
    },
    {
        "vanguard_blessing": _vanguard_blessing(
            occurrence_key="eotn.npc.ascalonian_refugee.dalada_uplands.-17566_469",
            interaction_mode="refresh", route_standoff_xy=(-17496.62, 566.91),
            target_xy=(-17566.0, 469.0), encoded_name="\\x8102\\x051B\\xD4BB\\xE595\\x3360",
            model_id=2036, target_name="Ascalonian Refugee",
        ),
        "path": _INITIAL_SWEEP[8:18],
    },
    {
        "vanguard_blessing": _vanguard_blessing(
            occurrence_key="eotn.npc.ascalonian_refugee.dalada_uplands.14918_-18156",
            interaction_mode="refresh", route_standoff_xy=(14819.72, -18087.15),
            target_xy=(14918.0, -18156.0), encoded_name="\\x8102\\x051B\\xD4BB\\xE595\\x3360",
            model_id=2036, target_name="Ascalonian Refugee",
        ),
        "path": _INITIAL_SWEEP[18:26],
    },
    {
        "vanguard_blessing": _vanguard_blessing(
            occurrence_key="eotn.npc.ascalonian_refugee.dalada_uplands.8655_-3971",
            interaction_mode="refresh", route_standoff_xy=(8742.41, -3888.78),
            target_xy=(8655.0, -3971.0), encoded_name="\\x8102\\x051B\\xD4BB\\xE595\\x3360",
            model_id=2036, target_name="Ascalonian Refugee",
        ),
        "path": _INITIAL_SWEEP[26:],
    },
    {
        "vanguard_blessing": _vanguard_blessing(
            occurrence_key="eotn.npc.ebon_vanguard_scout.dalada_uplands.-2641_449",
            interaction_mode="refresh", route_standoff_xy=(-2667.60, 331.99),
            target_xy=(-2641.0, 449.0), encoded_name="\\x8102\\x25A3\\xA4E9\\xF82A\\x7B52",
            model_id=6095, target_name="Ebon Vanguard Scout",
        ),
        "path": _SECOND_SWEEP,
    },
    {
        "vanguard_blessing": _vanguard_blessing(
            occurrence_key="eotn.npc.ebon_vanguard_scout.dalada_uplands.-3954_-11426",
            interaction_mode="refresh", route_standoff_xy=(-4038.88, -11510.82),
            target_xy=(-3954.0, -11426.0), encoded_name="\\x8101\\x57AF\\xDA83\\xD025\\x219D",
            model_id=6096, target_name="Ebon Vanguard Scout",
        ),
        "path": _THIRD_SWEEP,
    },
    {
        "vanguard_blessing": _vanguard_blessing(
            occurrence_key="eotn.npc.ascalonian_refugee.dalada_uplands.5884_11749",
            interaction_mode="refresh", route_standoff_xy=(5802.86, 11660.59),
            target_xy=(5884.0, 11749.0), encoded_name="\\x8102\\x0433\\xEC61\\x8B65\\x3147",
            model_id=2037, target_name="Ascalonian Refugee",
        ),
        "path": [(4666.3, 10422.2), (1772.7, 13212.8)],
    },
]

Dalada_Uplands_outpost_path = [(-16016, 17340), (-15400, 13500)]

Dalada_Uplands_ids = {
    "outpost_id": 648,
    "map_id": 647,
}
