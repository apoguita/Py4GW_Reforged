from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import ModuleType

_ROOT = Path(__file__).resolve().parents[2]
for package_name, package_path in (
    ("Py4GWCoreLib", _ROOT / "Py4GWCoreLib"),
    ("Py4GWCoreLib.modular", _ROOT / "Py4GWCoreLib/modular"),
    ("Py4GWCoreLib.modular.domain", _ROOT / "Py4GWCoreLib/modular/domain"),
):
    package = ModuleType(package_name)
    package.__path__ = [str(package_path)]  # type: ignore[attr-defined]
    sys.modules.setdefault(package_name, package)

from Py4GWCoreLib.modular.domain.interaction_catalog import InteractionCatalog


class InteractionCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = InteractionCatalog()

    def test_complete_catalog_loads(self) -> None:
        self.assertEqual(len(self.catalog.identities), 341)
        self.assertEqual(len(self.catalog.occurrences), 458)

    def test_existing_target_registry_identity_is_reused(self) -> None:
        identity = self.catalog.get_identity("nightfall.npc.goren.enc_8101_38df")
        self.assertIsNotNone(identity)
        assert identity is not None
        self.assertEqual(identity.target_registry_reference, ("npc", "GOREN", 0))
        self.assertEqual(identity.encoded_name_units, (0x8101, 0x38DF))

    def test_occurrence_resolves_identity_and_geometry(self) -> None:
        occurrence = self.catalog.get_occurrence("nightfall.npc.goren.dasha_vestibule.1827_-18489")
        self.assertEqual(occurrence.map_id, 434)
        self.assertEqual(occurrence.identity.display_name, "Goren")
        self.assertEqual(occurrence.target_xy, (1827.47, -18489.21))
        self.assertEqual(occurrence.binding.partition, "nightfall_dasha")
        self.assertEqual(len(occurrence.binding.partition_sha256), 64)

    def test_map_and_kind_filter(self) -> None:
        occurrences = tuple(self.catalog.iter_occurrences(map_id=404, kind="npc"))
        self.assertTrue(occurrences)
        self.assertTrue(all(item.map_id == 404 for item in occurrences))
        self.assertTrue(all(item.identity.kind == "npc" for item in occurrences))

    def test_unknown_occurrence_fails_closed(self) -> None:
        with self.assertRaisesRegex(KeyError, "unknown interaction occurrence"):
            self.catalog.get_occurrence("missing.occurrence")


if __name__ == "__main__":
    unittest.main()
