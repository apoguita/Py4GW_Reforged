from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "Sources/aC_Scripts/PyQuishAI_maps/Factions_TheJadeSea/GyalaHatchery.py"


def _load_route():
    spec = importlib.util.spec_from_file_location("gyala_hatchery_route", ROUTE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gyala_route_bakes_the_luxon_blessing_before_movement():
    module = _load_route()
    assert module.GyalaHatchery[0] == {
        "bless": {
            "name": "Take the Luxon blessing",
            "faction": "luxon",
            "target_xy": (7631.0, -19239.0),
        }
    }
    assert list(module.GyalaHatchery[1]) == ["path"]


def test_gyala_route_geometry_and_map_identity_are_frozen():
    module = _load_route()
    points = module.GyalaHatchery[1]["path"]
    digest = hashlib.sha256(json.dumps(points, separators=(",", ":")).encode()).hexdigest()
    assert len(points) == 58
    assert digest == "44a4384bdb0541e47525a4bd2fc915646439e8c8711cf1992367c3c14c79b10d"
    assert module.GyalaHatchery_ids == {"outpost_id": 279, "map_id": 144}
    assert module.GyalaHatchery_outpost_path == [(9177, -20845), (8500, -19800)]
