from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "Sources/aC_Scripts/PyQuishAI_maps/NF_Kourna/TheFloodplainOfMahnkelon.py"

EXPECTED_OCCURRENCES = {
    "USER-20261116-MAHNKELON-BLESSING-1": ((-19169.0, -13401.0), (-19166.81, -13470.41), 5434, "\\x8101\\x5254\\x81F0\\x39D0", (1837, 1838, 1977, 1978)),
    "USER-20261116-MAHNKELON-BLESSING-2": ((-5874.0, -11335.0), (-5953.97, -11296.96), 5434, "\\x8101\\x5226\\x90A1\\x9D78\\x5DA3", (1790, 1835, 1836, 1975, 1976)),
    "USER-20261116-MAHNKELON-BLESSING-3": ((13428.0, 1475.0), (13508.09, 1445.17), 5434, "\\x8101\\x521B\\xBB76\\x9793\\x0373", (1822, 1823, 1824, 1825, 1850, 1959, 1960, 2043, 2044)),
    "USER-20261116-MAHNKELON-BLESSING-4": ((-647.0, 11744.0), (-671.76, 11817.16), 5435, "\\x8101\\x521E\\xCB69\\x5812", (1793, 1829, 1830, 1967, 1968)),
}


def _load():
    spec = importlib.util.spec_from_file_location("floodplain_route", ROUTE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_floodplain_occurrences_are_baked_and_match_all_four_captures():
    module = _load()
    observed = {}
    for entry in module.TheFloodplainOfMahnkelon:
        blessing = entry["bless"]
        assert "catalog_occurrence" not in blessing
        assert blessing["interaction_mode"] == "first"
        assert blessing["target_name"] == "Wandering Priest"
        assert blessing["route_standoff_xy"] == blessing["player_approach_xy"]
        assert math.dist(blessing["target_xy"], blessing["player_approach_xy"]) < 100
        observed[blessing["capture_id"]] = (
            blessing["target_xy"],
            blessing["player_approach_xy"],
            blessing["model_id"],
            blessing["encoded_name"],
            blessing["effect_ids"],
        )
    assert observed == EXPECTED_OCCURRENCES


def test_floodplain_geometry_outpost_route_and_metadata_are_frozen():
    module = _load()
    route_entries = [
        (key, value)
        for entry in module.TheFloodplainOfMahnkelon
        for key, value in entry.items()
        if key in {"path", "literal_path"}
    ]
    points = [point for _key, value in route_entries for point in value]
    assert len(module.TheFloodplainOfMahnkelon) == 4
    assert len(points) == 82
    assert hashlib.sha256(json.dumps(route_entries, separators=(",", ":")).encode()).hexdigest() == "3f5beb854fd0c9b1b37ea645fbdd2826a961a593858cfea218f1d79d80a6a6ea"
    assert hashlib.sha256(json.dumps(points, separators=(",", ":")).encode()).hexdigest() == "f04b009e4f8c92fb4218f334f97df28704ee433da86faebe6131cb4d75f10084"
    assert module.TheFloodplainOfMahnkelon_outpost_path == [
        (206.72, 1511.54), (71.34, 1852.07), (482.83, 2143.01),
        (897.72, 2429.09), (1303.28, 2728.32), (1723.19, 3006.65),
        (2151.2, 3272.78), (2621.13, 3445.44), (3124.82, 3431.84),
        (3620.55, 3343.87), (4019.08, 3652.56), (4368.92, 4016.34),
        (4522.98, 4181.55), (4800, 4600),
    ]
    assert module.TheFloodplainOfMahnkelon_ids == {"outpost_id": 424, "map_id": 384}
