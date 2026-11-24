from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "Sources/aC_Scripts/PyQuishAI_maps/EOTN_Tarnished_Coast/ArborBay.py"

EXPECTED_OCCURRENCES = {
    "Arbor Bay entrance Asuran blessing": ((15806.97, 11963.51), (16314.79, 11640.41), (16362.0, 11627.0), 6826, "NPC-20260914-205818-818"),
    "Arbor Bay Asuran blessing 2": ((11087.62, -18114.26), (11087.62, -18114.26), (11134.0, -18131.0), 6806, "ROUTE-20260924-172315-274:Talk to Blessing"),
    "Arbor Bay Asuran blessing 3": ((-16668.76, -18866.15), (-16672.0, -18898.0), (-16672.0, -18898.0), 6826, "USER-SCREENSHOT-20260924-M6826-X-16672-Y-18898"),
    "Arbor Bay Asuran blessing 4": ((-15603.82, -4775.26), (-15630.0, -4698.0), (-15630.0, -4698.0), 6807, "USER-SCREENSHOT-20260924-M6807-X-15630-Y-4698"),
    "Arbor Bay Asuran blessing 5": ((-16516.73, 9803.07), (-16373.0, 9830.0), (-16373.0, 9830.0), 6801, "USER-SCREENSHOT-20260924-M6801-X-16373-Y9830"),
    "Arbor Bay Asuran blessing 6": ((-3060.54, 14263.56), (-2945.31, 14203.57), (-2939.0, 14220.0), 6806, "NPC-20260914-210219-026"),
    "Arbor Bay Asuran blessing 7": ((11757.11, 146.09), (11736.0, 70.0), (11736.0, 70.0), 6807, "USER-SCREENSHOT-20260924-M6807-X11736-Y70"),
    "Arbor Bay Asuran blessing 8": ((-3955.05, -10383.03), (-4128.0, -10433.0), (-4128.0, -10433.0), 6830, "USER-SCREENSHOT-20260924-M6830-X-4128-Y-10433"),
}

EXPECTED_CARTOGRAPHY_HOLD = {
    "name": "AB: Carto Face South",
    "xy": (18391.0, -15304.99),
    "facing_angle": -0.7853981633974483,
    "hold_ms": 1250,
    "position_tolerance": 25.0,
    "angle_tolerance": 0.15,
    "location_capture_id": "LOC-20260924-125832-192",
}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_arbor_bay_occurrences_match_all_eight_captures():
    module = _load(ROUTE, "arbor_occurrences")
    observed = {}
    kinds = []
    for key, value in module.ArborBay[0]:
        kinds.append(key)
        if key != "asuran_blessing":
            continue
        assert value["interaction_mode"] in {"first", "refresh"}
        assert tuple(value["effect_ids"]) == tuple(module.ARBOR_BAY_BLESSING_EFFECT_IDS)
        observed[value["name"]] = (
            value["route_standoff_xy"],
            value["player_approach_xy"],
            value["target_xy"],
            value["model_id"],
            value["capture_id"],
        )
    assert observed == EXPECTED_OCCURRENCES
    assert sum(
        value["interaction_mode"] == "first"
        for key, value in module.ArborBay[0]
        if key == "asuran_blessing"
    ) == 1
    assert "bless" not in kinds
    assert "continuous_path" not in kinds


def test_arbor_bay_geometry_and_cartography_hold_are_frozen():
    module = _load(ROUTE, "arbor_geometry")
    segment = module.ArborBay[0]
    points = [point for key, value in segment if key == "path" for point in value]
    holds = [value for key, value in segment if key == "face_hold"]
    digest = hashlib.sha256(json.dumps(points, separators=(",", ":")).encode()).hexdigest()
    assert len(segment) == 18
    assert len(points) == 274
    assert digest == "a871db8f6879e15fb4ed147d419064bb8d38de6e57608510dd9461830b6e9736"
    assert holds == [EXPECTED_CARTOGRAPHY_HOLD]
    assert module.ArborBay_outpost_path == [(16129.67, 14160.49), (15545.26, 12675.66)]
    assert module.ArborBay_ids == {"outpost_id": 624, "map_id": 485}


# Shared blessing and route-control behavior is validated by dependent PRs #192 and #195.
