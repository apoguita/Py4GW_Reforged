from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "Sources/aC_Scripts/PyQuishAI_maps/EOTN_Tarnished_Coast/SparkflySwamp.py"

EXPECTED_EFFECT_IDS = (
    2445, 2446, 2447, 2448, 2549, 2565, 2566, 2567, 2568,
    2457, 2458, 2459, 2460, 2550, 2578,
    2434, 2435, 2436, 2481, 2548, 2552,
    2469, 2470, 2471, 2472, 2551, 2591, 2592, 2593, 2594,
)

EXPECTED_OCCURRENCES = {
    "user-sparkfly-1": ((-8950, -19843), (-8977.91, -19842.77), 6806, "\\x8102\\x2423\\x8B55\\x9EC9\\x215C"),
    "user-sparkfly-2": ((-4550, 15959), (-4567.65, 16033.37), 6806, "\\x8102\\x2423\\x8B55\\x9EC9\\x215C"),
    "user-sparkfly-3": ((10582, 24346), (10565.08, 24313.17), 6806, "\\x8102\\x2423\\x8B55\\x9EC9\\x215C"),
    "user-sparkfly-4": ((8634, -11189), (8653.54, -11127.11), 6806, "\\x8102\\x2423\\x8B55\\x9EC9\\x215C"),
    "user-sparkfly-5": ((12542, -22714), (12507.74, -22684.0), 6807, "\\x8102\\x2418\\x85E2\\xE9EE\\x2988"),
    "user-sparkfly-6": ((-5244, -3222), (-5282.61, -3235.08), 6807, "\\x8102\\x2418\\x85E2\\xE9EE\\x2988"),
    "user-sparkfly-7": ((4770, 6679), (4802.82, 6726.96), 6807, "\\x8102\\x2418\\x85E2\\xE9EE\\x2988"),
}


def _load():
    spec = importlib.util.spec_from_file_location("sparkfly_route", ROUTE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sparkfly_occurrences_are_localized_and_match_all_seven_captures():
    module = _load()
    blessings = []
    for entry in module.SparkflySwamp:
        assert "asuran_blessing_v2" not in entry
        blessing = entry.get("asuran_blessing")
        if blessing is None:
            continue
        assert "catalog_occurrence" not in blessing
        assert blessing["buttons"] == 0
        assert blessing["target_name"] == "Weapon Krewe Member"
        assert blessing["effect_ids"] == EXPECTED_EFFECT_IDS
        blessings.append(blessing)

    assert len(blessings) == 7
    assert blessings[0]["interaction_mode"] == "first"
    assert all(item["interaction_mode"] == "refresh" for item in blessings[1:])
    assert {
        item["capture_id"]: (
            item["target_xy"],
            item["player_approach_xy"],
            item["model_id"],
            item["encoded_name"],
        )
        for item in blessings
    } == EXPECTED_OCCURRENCES


def test_sparkfly_geometry_and_map_metadata_are_frozen():
    module = _load()
    route_entries = [
        (key, value)
        for entry in module.SparkflySwamp
        for key, value in entry.items()
        if key in {"path", "literal_path"}
    ]
    points = [point for _key, value in route_entries for point in value]
    route_digest = hashlib.sha256(json.dumps(route_entries, separators=(",", ":")).encode()).hexdigest()
    point_digest = hashlib.sha256(json.dumps(points, separators=(",", ":")).encode()).hexdigest()

    assert len(module.SparkflySwamp) == 30
    assert sum("path" in entry for entry in module.SparkflySwamp) == 19
    assert sum("literal_path" in entry for entry in module.SparkflySwamp) == 4
    assert len(points) == 294
    assert route_digest == "682fdb8425504c8aec9b0db31abfc45ab2fdf64f9176438bac58a3174912c623"
    assert point_digest == "e8673e68d8c698fb2de5a24af7a5f5f34601c79d586defb734dedf3d8ec625f8"
    assert module.SparkflySwamp_outpost_path == [
        (-9673.29, -22652.21),
        (-9774.56, -22162.1),
        (-9712.22, -21662.88),
        (-9644.17, -21162.92),
        (-9576.08, -20664.99),
        (-9690.0, -18500.0),
    ]
    assert module.SparkflySwamp_ids == {"outpost_id": 638, "map_id": 558}
