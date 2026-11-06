from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "Sources/aC_Scripts/PyQuishAI_maps/EOTN_Far_Silverpeaks/Drakkar_Lake.py"

EXPECTED_OCCURRENCES = {
    "Drakkar Lake - Durdan Cliffjumper": ((7367.0, 23752.0), 6425, "user-20261010-screenshot-9"),
    "Drakkar Lake - Sonya the Crimson": ((-11603.0, 24975.0), 6431, "user-20261010-screenshot-1"),
    "Drakkar Lake - Beojorn": ((-5160.0, -4251.0), 6428, "user-20261010-screenshot-3"),
    "Drakkar Lake - Gafir Yogsson": ((-11560.0, -20852.0), 6425, "user-20261010-screenshot-4"),
    "Drakkar Lake - Valka Beastcrusher": ((5897.0, -23446.0), 6431, "user-20261010-screenshot-5"),
    "Drakkar Lake - Mandof": ((15233.0, -17127.0), 6425, "user-20261010-screenshot-6"),
    "Drakkar Lake - Wiglaf": ((14523.0, 2357.0), 6425, "user-20261010-screenshot-7"),
    "Drakkar Lake - Ruven": ((12338.0, 16844.0), 6425, "user-20261010-screenshot-8"),
    "Drakkar Lake - Ion Thomsson": ((4297.0, 5538.0), 6425, "user-20261010-screenshot-10"),
}

ORIGINAL_SWEEP_SHA256 = "0b1b0b9f97af084ffab4eedf8d4eccdf5ec5b8c8a7904f2b6fa563aad96abb3a"
DETOUR = [
    (6568.99, -13832.35),
    (6321.83, -14271.61),
    (6009.84, -14671.32),
    (6164.83, -15154.93),
    (6352.20, -15620.13),
    (6532.11, -16135.91),
    (6572.55, -16251.85),
]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_drakkar_occurrences_are_exact_and_route_owned():
    module = _load(ROUTE, "drakkar_route")
    observed = {}
    for entry in module.Drakkar_Lake:
        blessing = entry.get("norn_blessing")
        if blessing is None:
            continue
        assert blessing["interaction_mode"] == "norn_challenge"
        assert blessing["player_approach_xy"] == blessing["route_standoff_xy"]
        assert blessing["encoded_name"]
        assert tuple(blessing["effect_ids"]) == tuple(module.NORN_HUNTING_PARTY_EFFECT_IDS)
        observed[blessing["name"]] = (
            blessing["target_xy"],
            blessing["model_id"],
            blessing["capture_id"],
        )
    assert observed == EXPECTED_OCCURRENCES


def test_drakkar_preserves_original_sweep_and_adds_captured_detour():
    module = _load(ROUTE, "drakkar_route_geometry")
    main_entries = [module.Drakkar_Lake[0], *module.Drakkar_Lake[3:]]
    main_points = [point for entry in main_entries for point in entry.get("path", ())]
    original_points = [
        point for point in main_points
        if all(isinstance(coordinate, int) for coordinate in point)
    ]
    digest = hashlib.sha256(
        json.dumps(original_points, separators=(",", ":")).encode()
    ).hexdigest()
    assert len(original_points) == 86
    assert digest == ORIGINAL_SWEEP_SHA256
    assert main_points[
        main_points.index((8563, -7658)) + 1:main_points.index((5956, -16580))
    ] == DETOUR


def test_sonya_addendum_is_forward_then_exact_reverse():
    module = _load(ROUTE, "drakkar_route_sonya")
    assert len(module.SONYA_OUTBOUND_ROUTE) == 15
    assert module.Drakkar_Lake[1]["path"] is module.SONYA_OUTBOUND_ROUTE
    assert module.Drakkar_Lake[2]["path"] == list(reversed(module.SONYA_OUTBOUND_ROUTE))
    assert module.Drakkar_Lake[1]["norn_blessing"]["target_name"] == "Sonya the Crimson"


# Shared owner and adapter behavior are validated by dependent PRs #148 and #192.
