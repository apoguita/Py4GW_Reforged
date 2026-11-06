from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "Sources/aC_Scripts/PyQuishAI_maps/EOTN_Charr_Homelands/Dalada_Uplands.py"

EXPECTED_OCCURRENCES = {
    "eotn.npc.ascalonian_refugee.dalada_uplands.-14971_11013":
        ("first", (-14971.0, 11013.0), 2037),
    "eotn.npc.ascalonian_refugee.dalada_uplands.-17566_469":
        ("refresh", (-17566.0, 469.0), 2036),
    "eotn.npc.ascalonian_refugee.dalada_uplands.14918_-18156":
        ("refresh", (14918.0, -18156.0), 2036),
    "eotn.npc.ascalonian_refugee.dalada_uplands.8655_-3971":
        ("refresh", (8655.0, -3971.0), 2036),
    "eotn.npc.ebon_vanguard_scout.dalada_uplands.-2641_449":
        ("refresh", (-2641.0, 449.0), 6095),
    "eotn.npc.ebon_vanguard_scout.dalada_uplands.-3954_-11426":
        ("refresh", (-3954.0, -11426.0), 6096),
    "eotn.npc.ascalonian_refugee.dalada_uplands.5884_11749":
        ("refresh", (5884.0, 11749.0), 2037),
}


def _load_route():
    spec = importlib.util.spec_from_file_location("dalada_route", ROUTE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dalada_occurrences_are_exact_and_route_owned():
    module = _load_route()
    entries = module.Dalada_Uplands
    assert len(entries) == 7

    observed = {}
    for entry in entries:
        assert set(entry) == {"vanguard_blessing", "path"}
        blessing = entry["vanguard_blessing"]
        assert blessing["buttons"] == 0
        assert blessing["player_approach_xy"] == blessing["route_standoff_xy"]
        assert blessing["encoded_name"]
        assert blessing["effect_ids"] == module.VANGUARD_PATROL_EFFECT_IDS
        observed[blessing["occurrence_key"]] = (
            blessing["interaction_mode"],
            blessing["target_xy"],
            blessing["model_id"],
        )

    assert observed == EXPECTED_OCCURRENCES
    assert sum(
        entry["vanguard_blessing"]["interaction_mode"] == "first"
        for entry in entries
    ) == 1


def test_dalada_preserves_installed_sweep_partitioning():
    module = _load_route()
    path_lengths = [len(entry["path"]) for entry in module.Dalada_Uplands]
    assert path_lengths == [8, 10, 8, 49, 15, 15, 2]
    assert module.Dalada_Uplands[0]["path"][0] == (-14350.5, 12790.6)
    assert module.Dalada_Uplands[-1]["path"][-1] == (1772.7, 13212.8)


# Shared adapter behavior is validated by dependent PR #192.
