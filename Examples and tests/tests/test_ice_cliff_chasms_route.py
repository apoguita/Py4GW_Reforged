from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "Sources/aC_Scripts/PyQuishAI_maps/EOTN_Far_Silverpeaks/Ice_Cliff_Chasms.py"
NOTICE = ROOT / "Sources/aC_Scripts/PyQuishAI_maps/THIRD_PARTY_NOTICES.md"

EXPECTED_OCCURRENCES = {
    "Tjorvi Throstson": ((2835.69, -24503.93), (2759.0, -24485.0), 6425, "\\x8102\\x24CB\\x82C4\\xF001\\x46BB", "user-20261024-ice-cliff-1"),
    "Nidbjorg": ((2479.92, -15529.58), (2401.0, -15537.0), 6425, "\\x8102\\x24C6\\xE0F0\\xA881\\x33A4", "user-20261024-ice-cliff-2"),
    "Skjaldulf Lightfingers": ((7103.54, -9486.42), (7174.0, -9465.0), 6431, "\\x8102\\x24C1\\xEC50\\xEF04\\x248F", "user-20261024-ice-cliff-3"),
    "Ragnvald": ((-7598.79, -2266.41), (-7659.0, -2221.0), 6425, "\\x8102\\x24BC\\xD689\\x92E9\\x0E9A", "user-20261024-ice-cliff-4"),
    "Ogg the Gruff": ((3864.92, 4974.48), (3913.0, 5035.0), 6425, "\\x8102\\x24B7\\xA1FA\\xF373\\x1B76", "user-20261024-ice-cliff-5"),
    "Ornoloff": ((5378.42, 12012.69), (5389.0, 11922.0), 6425, "\\x8102\\x24B2\\xA363\\x4517", "user-20261024-ice-cliff-6"),
    "Maddi Ingvendottir": ((10301.41, 25276.12), (10313.0, 25359.0), 6431, "\\x8102\\x24AD\\xAE92\\xA676\\x735E", "user-20261024-ice-cliff-7"),
    "Ketilbiorn": ((-2461.05, 23756.44), (-2469.0, 23809.0), 6425, "\\x8102\\x24A8\\xD7CB\\xCB95\\x140B", "user-20261024-ice-cliff-8"),
}

CRYSTAL_GO_AROUND = [
    (7867.58, 17604.54), (8375.47, 17559.55), (8862.6, 17682.48),
    (9206.4, 18046.73), (9259.54, 18554.03), (9164.29, 19053.21),
    (8753.92, 19349.07), (8227.92, 19402.62), (7727.57, 19327.08),
    (7307.3, 19055.37), (7043.76, 18625.94), (7029.25, 18117.17),
    (7235.78, 17657.29), (7639.22, 17353.01), (8130.8, 17222.34),
    (8254.31, 17215.9),
]

CRYSTAL_DETOUR = [
    (8024.17, 17400.49), (8567.81, 17564.26), (8992.39, 17834.43),
    (9286.57, 18241.32), (9399.57, 18739.34), (9442.09, 19160.05),
    (8820.0, 20033.0),
]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ice_cliff_occurrences_match_all_eight_captures():
    module = _load(ROUTE, "ice_cliff_occurrences")
    observed = {}
    for entry in module.Ice_Cliff_Chasms:
        assert "bless" not in entry
        blessing = entry.get("norn_blessing")
        if blessing is None:
            continue
        assert blessing["interaction_mode"] == "norn_challenge"
        assert blessing["player_approach_xy"] == blessing["route_standoff_xy"]
        assert tuple(blessing["effect_ids"]) == tuple(module.NORN_HUNTING_PARTY_EFFECT_IDS)
        observed[blessing["target_name"]] = (
            blessing["route_standoff_xy"], blessing["target_xy"],
            blessing["model_id"], blessing["encoded_name"], blessing["capture_id"],
        )
    assert observed == EXPECTED_OCCURRENCES


def test_ice_cliff_route_geometry_and_captured_crystal_detours_are_frozen():
    module = _load(ROUTE, "ice_cliff_geometry")
    points = [point for entry in module.Ice_Cliff_Chasms for point in entry.get("path", ())]
    digest = hashlib.sha256(json.dumps(points, separators=(",", ":")).encode()).hexdigest()
    assert len(module.Ice_Cliff_Chasms) == 67
    assert len(points) == 183
    assert digest == "84d6ab0048016eb7ddac92c673938c3f1f086aa7d1aae4510a6dfa33a5619490"
    assert any(entry.get("path") == CRYSTAL_GO_AROUND for entry in module.Ice_Cliff_Chasms)
    assert any(entry.get("path") == CRYSTAL_DETOUR for entry in module.Ice_Cliff_Chasms)
    assert module.Ice_Cliff_Chasms_ids == {"outpost_id": 675, "map_id": 499}


def test_ice_cliff_donor_provenance_and_mit_notice_are_present():
    source = ROUTE.read_text(encoding="utf-8")
    notice = NOTICE.read_text(encoding="utf-8")
    donor_commit = "330b8f505d3b5efe3dec0edb5dbf3afb387b0b98"
    assert "mrdomrocks/Guild-Wars-Vanquish-Bot" in source
    assert donor_commit in source
    assert "ROUTE-20261024-103405-626" in source
    assert "ROUTE-20261024-103238-315" in source
    assert donor_commit in notice
    assert "Copyright (c) 2026 mrdomrocks" in notice
    assert "Permission is hereby granted, free of charge" in notice

# Shared owner and adapter behavior are validated by dependent PRs #148 and #192.
