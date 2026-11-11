from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "Sources/aC_Scripts/PyQuishAI_maps/Factions_EchovaldForest/MourningVeilFalls.py"


def _load():
    spec = importlib.util.spec_from_file_location("mourning_veil_falls_route", ROUTE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mourning_veil_falls_localizes_the_captured_kurzick_priest():
    module = _load()
    blessing_entry, path_entry = module.MourningVeilFalls
    assert set(blessing_entry) == {"faction_blessing"}
    assert set(path_entry) == {"path"}

    blessing = blessing_entry["faction_blessing"]
    assert blessing == {
        "name": "Take the Kurzick blessing",
        "faction": "kurzick",
        "target_xy": (-16475.0, -6496.0),
        "encoded_name": "\\x3E98\\xAA38\\x045D",
        "model_id": 3477,
        "target_name": "Kurzick Priest",
        "captured_player_xy": (-16516.58, -6547.67),
        "capture_id": "USER-20261111-MOURNING-VEIL-KURZICK-PRIEST",
    }
    assert "catalog_occurrence" not in blessing


def test_mourning_veil_falls_preserves_the_original_route_and_map_metadata():
    module = _load()
    points = module.MourningVeilFalls[1]["path"]
    point_digest = hashlib.sha256(json.dumps(points, separators=(",", ":")).encode()).hexdigest()

    assert len(points) == 51
    assert point_digest == "4cf07504c1444266054e58651e68afe33e50d56fb897b676b1b0fb20880ac9df"
    assert points[0] == (-20006.83, -6088.50)
    assert points[-1] == (16624.41, 1737.03)
    assert module.MourningVeilFalls_outpost_path == [
        (-182, 223),
        (-39, 2572),
        (-4144, 4036),
        (-4637, 4991),
    ]
    assert module.MourningVeilFalls_ids == {"outpost_id": 230, "map_id": 209}
