from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "Sources/aC_Scripts/PyQuishAI_maps/Proph_Kryta/KessexPeak.py"

EXPECTED_REPLACE_1 = [
    (-1710.37, -2965.18),
    (-2216.31, -2984.49),
    (-2592.81, -3316.04),
    (-2724.37, -3532.89),
]

EXPECTED_REPLACE_2 = [
    (-1927.07, -10471.11),
    (-1824.02, -10713.4),
    (-1735.8, -10956.36),
    (-1631.84, -11185.43),
    (-1439.64, -11357.82),
    (-1191.38, -11320.39),
    (-955.27, -11234.87),
    (-732.02, -11121.31),
    (-510.73, -10999.86),
    (-256.8, -10968.17),
    (-13.29, -11051.59),
    (185.65, -11208.25),
    (426.26, -11277.09),
    (642.21, -11409.23),
    (844.49, -11567.49),
    (1003.1, -11763.29),
    (1149.68, -11967.28),
    (1281.73, -12180.12),
    (1454.46, -12368.26),
    (1618.72, -12567.4),
    (1818.15, -12721.39),
    (2054.88, -12822.36),
    (2527.95, -12990.67),
    (3006.48, -13136.59),
    (3503.94, -13210.05),
    (4007.95, -13176.61),
    (4487.21, -13025.66),
    (4954.58, -12830.78),
    (5438.08, -12695.93),
    (5921.91, -12551.37),
    (6398.59, -12393.6),
    (6876.8, -12544.82),
    (7176.03, -12949.3),
    (7482.79, -13348.56),
    (7718.82, -13796.49),
    (7903.1, -14265.3),
    (8101.53, -14725.14),
    (8277.33, -15198.45),
    (8412.76, -15682.24),
    (8530.58, -16175.29),
    (8422.46, -16664.32),
    (8259.05, -17137.2),
    (8088.37, -17617.64),
    (8040.55, -17873.2),
]


def _load():
    spec = importlib.util.spec_from_file_location("kessex_peak_route", ROUTE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_kessex_peak_uses_the_map_specific_ids():
    module = _load()
    assert module.KessexPeak_ids == {
        "outpost_id": 138,
        "map_id": 64,
        "transit_id": 18,
    }
    assert not hasattr(module, "CursedLands_ids")


def test_kessex_peak_transit_contains_both_captured_replacements_and_portal_tail():
    module = _load()
    transit = module.KessexPeak_transit_path

    assert len(transit) == 57
    assert transit[:5] == [
        (-5241, 15182),
        (-6837, 11715),
        (-7152, 7351),
        (156, 2791),
        (1680, 496),
    ]
    assert transit[5:9] == EXPECTED_REPLACE_1
    assert transit[9:11] == [(-3802, -4905), (-5955, -9211)]
    assert transit[11:55] == EXPECTED_REPLACE_2
    assert transit[-2:] == [(7834, -18238), (6093, -18015)]
    assert (-753, -10986) not in transit
    assert (7797, -13034) not in transit
    assert (8548, -17166) not in transit


def test_kessex_peak_vanquish_route_and_outpost_path_are_unchanged():
    module = _load()
    vanquish_digest = hashlib.sha256(
        json.dumps(module.KessexPeak, separators=(",", ":")).encode()
    ).hexdigest()
    outpost_digest = hashlib.sha256(
        json.dumps(module.KessexPeak_outpost_path, separators=(",", ":")).encode()
    ).hexdigest()

    assert len(module.KessexPeak) == 55
    assert vanquish_digest == "6511539f09b8410d234955da4d0d582d83d28f11160a2a00011cf4af3837d1c3"
    assert outpost_digest == "2f3678b395bef9fcda49967a470077a9ddb28b821dad05b7b491a1cdb9c89318"
    assert hashlib.sha256(
        json.dumps(module.KessexPeak_transit_path, separators=(",", ":")).encode()
    ).hexdigest() == "e1c4fdf0dce6d9bfbb657cc8352b9baae906b03491b4dbcfb1196dc72f876caf"
