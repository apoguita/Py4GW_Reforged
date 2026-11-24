from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "Sources/aC_Scripts/PyQuishAI_maps/EOTN_Tarnished_Coast/RivenEarth.py"

EXPECTED_EFFECT_IDS = (2434, 2435, 2436, 2481, 2548, 2552, 2553, 2554, 2555, 2556)

EXPECTED_OCCURRENCES = {
    "Talk to the Sky Krewe member (1)": ((-24272, -5719), (-24272.52, -5644.63), 0, 6806, "\\x8102\\x240D\\xFEF0\\xC41A\\x1619"),
    "Talk to the Sky Krewe member (2)": ((-7937, -11515), (-7999.44, -11509.44), 0, 6807, "\\x8102\\x2401\\xD33A\\xE941\\x11A4"),
    "Talk to the Sky Krewe member (3)": ((-3119, -467), (-3149.93, -429.45), 0, 6806, "\\x8102\\x240D\\xFEF0\\xC41A\\x1619"),
    "Talk to the Sky Krewe member (4)": ((-16300, 9977), (-16340.29, 9948.84), 0, 6807, "\\x8102\\x2401\\xD33A\\xE941\\x11A4"),
    "Talk to the Sky Krewe member (5)": ((-3054, 12916), (-3087.07, 12857.41), 0, 6806, "\\x8102\\x240D\\xFEF0\\xC41A\\x1619"),
    "Talk to the Sky Krewe member (6)": ((23718, -491), (23704.69, -470.65), 0, 6806, "\\x8102\\x240D\\xFEF0\\xC41A\\x1619"),
    "Talk to the Sky Krewe member (7)": ((11437, 8695), (11472.34, 8721.34), 0, 6807, "\\x8102\\x2401\\xD33A\\xE941\\x11A4"),
    "Talk to the Sky Krewe member (8)": ((9246, -8524), (9307.49, -8499.88), 0, 6807, "\\x8102\\x2401\\xD33A\\xE941\\x11A4"),
}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_riven_earth_occurrences_match_all_eight_captures():
    module = _load(ROUTE, "riven_occurrences")
    observed = {}
    for entry in module.RivenEarth:
        assert "asuran_blessing_v2" not in entry
        blessing = entry.get("asuran_blessing")
        if blessing is None:
            continue
        observed[blessing["name"]] = (
            blessing["target_xy"],
            blessing["player_approach_xy"],
            blessing["buttons"],
            blessing["model_id"],
            blessing["encoded_name"],
        )
        assert blessing["target_name"] == "Sky Krewe Member"
        assert blessing["effect_ids"] == EXPECTED_EFFECT_IDS
        assert blessing["interaction_mode"] in {"first", "refresh"}
    assert observed == EXPECTED_OCCURRENCES
    assert (blessings := [entry["asuran_blessing"] for entry in module.RivenEarth if "asuran_blessing" in entry])
    assert blessings[0]["interaction_mode"] == "first"
    assert all(item["interaction_mode"] == "refresh" for item in blessings[1:])


def test_riven_earth_geometry_and_literal_segments_are_frozen():
    module = _load(ROUTE, "riven_geometry")
    route_entries = [
        (key, value)
        for entry in module.RivenEarth
        for key, value in entry.items()
        if key in {"path", "literal_path"}
    ]
    points = [point for _key, value in route_entries for point in value]
    route_digest = hashlib.sha256(json.dumps(route_entries, separators=(",", ":")).encode()).hexdigest()
    point_digest = hashlib.sha256(json.dumps(points, separators=(",", ":")).encode()).hexdigest()
    assert len(module.RivenEarth) == 121
    assert sum("path" in entry for entry in module.RivenEarth) == 98
    assert sum("literal_path" in entry for entry in module.RivenEarth) == 15
    assert len(points) == 230
    assert route_digest == "f8e7113986da413c26a21b9d7116215c257da6e4525f734bd78086fdb1cf400a"
    assert point_digest == "3d4817149864597fcc4f5e3699101a4d20939c3c562018e9ee06ec78cc4b4e70"
    assert module.RivenEarth_outpost_path == [(19623, 16850), (20300, 16850)]
    assert module.RivenEarth_ids == {"outpost_id": 640, "map_id": 501}
