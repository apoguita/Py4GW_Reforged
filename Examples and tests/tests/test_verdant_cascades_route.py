from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "Sources/aC_Scripts/PyQuishAI_maps/EOTN_Tarnished_Coast/VerdantCascades.py"

EXPECTED_EFFECT_IDS = (2434, 2435, 2436, 2481, 2548, 2552, 2553, 2554, 2555, 2556)

EXPECTED_OCCURRENCES = {
    "Talk to the Purifier Krewe member (1)": ((-20294, 6576), (-20294, 6576), 6807, "\\x8102\\x242E\\xAFE2\\xD572\\x0FB8"),
    "Talk to the Purifier Krewe member (2)": ((-17292, -8270), (-17310.93, -8218.15), 6806, "\\x8102\\x243A\\xEAE7\\xD057\\x4DC7"),
    "Talk to the Purifier Krewe member (3)": ((-700, -7661), (-705.53, -7747.18), 6807, "\\x8102\\x242E\\xAFE2\\xD572\\x0FB8"),
    "Talk to the Purifier Krewe member (4)": ((-7420, 14680), (-7346.09, 14734.17), 6806, "\\x8102\\x243A\\xEAE7\\xD057\\x4DC7"),
    "Talk to the Purifier Krewe member (5)": ((2186, 7178), (2186, 7178), 6807, "\\x8102\\x242E\\xAFE2\\xD572\\x0FB8"),
    "Talk to the Purifier Krewe member (6)": ((12581, 3435), (12563.45, 3478.9), 6807, "\\x8102\\x242E\\xAFE2\\xD572\\x0FB8"),
    "Talk to the Purifier Krewe member (7)": ((23325, -9221), (23302.59, -9221.25), 6806, "\\x8102\\x243A\\xEAE7\\xD057\\x4DC7"),
    "Talk to the Purifier Krewe member (8)": ((25132, 11062), (25066.21, 11087.24), 6806, "\\x8102\\x243A\\xEAE7\\xD057\\x4DC7"),
}


def _load():
    spec = importlib.util.spec_from_file_location("verdant_cascades_route", ROUTE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verdant_occurrences_are_baked_and_match_all_eight_captures():
    module = _load()
    blessings = []
    observed = {}
    for index, entry in enumerate(module.VerdantCascades):
        assert "asuran_blessing_v2" not in entry
        blessing = entry.get("asuran_blessing")
        if blessing is None:
            continue
        assert "catalog_occurrence" not in blessing
        assert blessing["buttons"] == 0
        assert blessing["target_name"] == "Purifier Krewe Member"
        assert blessing["effect_ids"] == EXPECTED_EFFECT_IDS
        assert module.VerdantCascades[index - 1]["literal_path"] == list(
            reversed(module.VerdantCascades[index + 1]["literal_path"])
        )
        observed[blessing["name"]] = (
            blessing["target_xy"],
            blessing["player_approach_xy"],
            blessing["model_id"],
            blessing["encoded_name"],
        )
        blessings.append(blessing)

    assert observed == EXPECTED_OCCURRENCES
    assert len(blessings) == 8
    assert blessings[0]["interaction_mode"] == "first"
    assert all(item["interaction_mode"] == "refresh" for item in blessings[1:])


def test_verdant_geometry_and_map_metadata_are_frozen():
    module = _load()
    route_entries = [
        (key, value)
        for entry in module.VerdantCascades
        for key, value in entry.items()
        if key in {"path", "literal_path"}
    ]
    points = [point for _key, value in route_entries for point in value]
    assert len(module.VerdantCascades) == 156
    assert sum("path" in entry for entry in module.VerdantCascades) == 129
    assert sum("literal_path" in entry for entry in module.VerdantCascades) == 19
    assert len(points) == 237
    assert hashlib.sha256(json.dumps(route_entries, separators=(",", ":")).encode()).hexdigest() == "d5959312e2eea7cc9337fc87847124e31332d3f8a6f00b5fb27f19cdc1723874"
    assert hashlib.sha256(json.dumps(points, separators=(",", ":")).encode()).hexdigest() == "2f04e2f6a702f571f83dec8dacc0960cdaf479b2fbc9823e0613e5e4d558ca7a"
    assert module.VerdantCascades_outpost_path == [(-22340, 10813), (-22785, 6107)]
    assert module.VerdantCascades_ids == {"outpost_id": 639, "map_id": 566}
