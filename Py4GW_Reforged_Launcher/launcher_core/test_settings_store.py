"""Unit tests for launcher_core/settings_store.py (RELAY 095, RELAY 098).

No committed test file existed for this module before now -- same "no test
existed, wrote one" situation this repo has hit before. Only covers what
each entry actually touched (window_geometry, then
window_title_rename_enabled) -- not backfilling coverage for the module's
other, pre-existing settings.

Run: .venv\\Scripts\\python.exe -m unittest launcher_core.test_settings_store -v
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from launcher_core import settings_store


class TestWindowGeometry(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "launcher_settings.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_none_when_nothing_saved_yet(self):
        """Caller (run_shell.main()) resolves its own hardcoded first-run
        default from this -- same "None means use the default" shape as
        load_mod_repo_path/load_custom_palette."""
        self.assertIsNone(settings_store.load_window_geometry(self.path))

    def test_round_trip(self):
        geometry = {"x": 12, "y": 34, "width": 601, "height": 817, "maximized": False}
        settings_store.save_window_geometry(geometry, self.path)
        self.assertEqual(settings_store.load_window_geometry(self.path), geometry)

    def test_save_preserves_other_settings_in_the_same_file(self):
        """Real bug this module's own docstring exists to prevent -- a save
        must merge into the existing file, not overwrite it wholesale."""
        settings_store.save_bulk_launch_pacing_seconds(20, self.path)
        settings_store.save_window_geometry({"x": 1, "y": 2, "width": 3, "height": 4, "maximized": True}, self.path)
        self.assertEqual(settings_store.load_bulk_launch_pacing_seconds(self.path), 20)
        self.assertEqual(settings_store.load_window_geometry(self.path)["maximized"], True)

    def test_maximized_round_trips_as_a_real_bool(self):
        settings_store.save_window_geometry(
            {"x": 0, "y": 0, "width": 601, "height": 817, "maximized": True}, self.path
        )
        geometry = settings_store.load_window_geometry(self.path)
        self.assertIs(geometry["maximized"], True)


class TestWindowTitleRenameEnabled(unittest.TestCase):
    """RELAY 098: Apo (Discord) -- "the launcher is forcefully renaming
    the clients at launch... doesnt seem to be a config option for this."
    Same default-True, no-behavior-change-on-upgrade shape as
    py4gw_injection_enabled/gmod_injection_enabled."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "launcher_settings.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_defaults_true_when_nothing_saved_yet(self):
        """Opt-out, not a new default-off feature -- an existing install
        upgrading to this must see zero behavior change until they
        actually flip it off."""
        self.assertTrue(settings_store.load_window_title_rename_enabled(self.path))

    def test_round_trip_false(self):
        settings_store.save_window_title_rename_enabled(False, self.path)
        self.assertFalse(settings_store.load_window_title_rename_enabled(self.path))

    def test_round_trip_true(self):
        settings_store.save_window_title_rename_enabled(False, self.path)
        settings_store.save_window_title_rename_enabled(True, self.path)
        self.assertTrue(settings_store.load_window_title_rename_enabled(self.path))

    def test_save_preserves_other_settings_in_the_same_file(self):
        settings_store.save_bulk_launch_pacing_seconds(20, self.path)
        settings_store.save_window_title_rename_enabled(False, self.path)
        self.assertEqual(settings_store.load_bulk_launch_pacing_seconds(self.path), 20)
        self.assertFalse(settings_store.load_window_title_rename_enabled(self.path))


if __name__ == "__main__":
    unittest.main()
