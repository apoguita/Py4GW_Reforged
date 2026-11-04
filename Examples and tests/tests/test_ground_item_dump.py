from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import unittest

ROOT = Path(__file__).resolve().parents[2]
WIDGET = ROOT / "Widgets/Coding/Debug/Py4GW/Ground Item Dump.py"


def load_evidence(*, player_error=False, item_model=42, core_model=42):
    def player_id():
        if player_error:
            raise RuntimeError("player unavailable")
        return 7
    item = SimpleNamespace(model_id=item_model, item_type=SimpleNamespace(ToInt=lambda: 29, GetName=lambda: "Bundle"), name="held", GetName=lambda: "held", GetSingleItemName=lambda: "held")
    ns: dict[str, Any] = {
        "Player": SimpleNamespace(GetAgentID=player_id),
        "Agent": SimpleNamespace(IsHoldingItem=lambda _: True, GetWeaponExtraData=lambda _: (200, 0, 0)),
        "PyItem": SimpleNamespace(PyItem=lambda _: item),
        "Item": SimpleNamespace(GetModelID=lambda _: core_model),
    }
    names = {"_render", "_try_value", "_evidence_line", "_build_held_slot_evidence"}
    tree = ast.parse(WIDGET.read_text(encoding="utf-8-sig"))
    nodes: list[ast.stmt] = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(WIDGET), "exec"), ns)
    return ns["_build_held_slot_evidence"]


class GroundItemEvidenceTests(unittest.TestCase):
    def test_held_identity_is_observed_separately_from_saved_ground_identity(self):
        text, summary = load_evidence()(100, 42)
        self.assertIn("held id matches captured item id", text)
        self.assertIn("exact held model 42", text)
        self.assertIn("held model matches captured ground model: YES", text)
        self.assertEqual(summary["held_item_id"], 200)

    def test_disagreeing_held_apis_do_not_claim_exact_model_proof(self):
        text, _ = load_evidence(item_model=42, core_model=43)(100, 42)
        self.assertIn("held model APIs disagree", text)
        self.assertIn("held model matches captured ground model: UNAVAILABLE", text)

    def test_failed_player_lookup_is_recorded_without_inventing_possession(self):
        text, summary = load_evidence(player_error=True)(100, 42)
        self.assertIn("player unavailable", text)
        self.assertIn("positive held-slot item ID unavailable", text)
        self.assertIsNone(summary["held_item_id"])


if __name__ == "__main__":
    unittest.main()
