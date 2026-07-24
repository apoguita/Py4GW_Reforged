"""Unit tests for launcher_core/gw1_launch.py's gMod graceful-skip fix (RELAY 091).

No committed test coverage existed for gw1_launch.py at all before this --
verified via a real search, not assumed (same situation RELAY 088 hit for
prereqs.py). The full launch pipeline is heavily Win32-coupled
(CreateProcessW, CreateRemoteThread, window polling), not something to mock
wholesale for a scope this small -- _resolve_gmod_launch_decision was pulled
out specifically so the actual decision logic is testable in isolation.

One regression test at the full launch_py4gw_profile level confirms the
py4gw_dll_path hard-fail (deliberately unchanged by this entry) still fires
before any process gets created -- that path doesn't touch Win32 either,
since it returns before CreateProcessW.

Run: .venv\\Scripts\\python.exe -m unittest launcher_core.test_gw1_launch -v
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from launcher_core import gw1_launch
from launcher_core.gw1_launch import _resolve_gmod_launch_decision, launch_py4gw_profile
from launcher_core.profile import GameProfile


class ResolveGmodLaunchDecisionTests(unittest.TestCase):
    def setUp(self):
        self.log: list = []

    def test_gmod_disabled_on_profile_returns_false_no_autodetect(self):
        profile = GameProfile(gmod_enabled=False, gmod_dll_path="")
        with patch.object(gw1_launch.mod_root, "find_dll_under_mod_root") as mock_detect:
            result = _resolve_gmod_launch_decision(profile, gmod_injection_enabled=True, log=self.log)
        self.assertFalse(result)
        mock_detect.assert_not_called()

    def test_gmod_disabled_globally_returns_false_no_autodetect(self):
        profile = GameProfile(gmod_enabled=True, gmod_dll_path="")
        with patch.object(gw1_launch.mod_root, "find_dll_under_mod_root") as mock_detect:
            result = _resolve_gmod_launch_decision(profile, gmod_injection_enabled=False, log=self.log)
        self.assertFalse(result)
        mock_detect.assert_not_called()

    def test_path_already_valid_returns_true_no_autodetect(self):
        with tempfile.NamedTemporaryFile(suffix=".dll", delete=False) as f:
            real_path = f.name
        try:
            profile = GameProfile(gmod_enabled=True, gmod_dll_path=real_path)
            with patch.object(gw1_launch.mod_root, "find_dll_under_mod_root") as mock_detect:
                result = _resolve_gmod_launch_decision(profile, gmod_injection_enabled=True, log=self.log)
            self.assertTrue(result)
            mock_detect.assert_not_called()
        finally:
            Path(real_path).unlink()

    def test_missing_path_autodetect_resolves_it_mutates_profile_and_logs(self):
        profile = GameProfile(gmod_enabled=True, gmod_dll_path="")
        with patch.object(gw1_launch.mod_root, "find_dll_under_mod_root", return_value="C:/found/gMod.dll") as mock_detect:
            result = _resolve_gmod_launch_decision(profile, gmod_injection_enabled=True, log=self.log)
        self.assertTrue(result)
        mock_detect.assert_called_once_with("gMod.dll")
        self.assertEqual(profile.gmod_dll_path, "C:/found/gMod.dll")
        self.assertTrue(any("auto-detected" in line for line in self.log))

    def test_missing_path_autodetect_still_fails_graceful_skip_not_hard_fail(self):
        """The core RELAY 091 behavior change: this used to hard-fail the
        whole launch (LaunchResult(False, ...)) -- now it's just a decision
        of False, with a clear log line, so the caller can proceed without
        gMod instead of aborting Py4GW injection too."""
        profile = GameProfile(gmod_enabled=True, gmod_dll_path="")
        with patch.object(gw1_launch.mod_root, "find_dll_under_mod_root", return_value=""):
            result = _resolve_gmod_launch_decision(profile, gmod_injection_enabled=True, log=self.log)
        self.assertFalse(result)
        self.assertEqual(profile.gmod_dll_path, "")  # not persisted from a failed redetect
        self.assertTrue(any("launching without gMod injection" in line for line in self.log))

    def test_stale_nonexistent_path_treated_same_as_empty(self):
        """A saved path that doesn't exist on disk anymore (not just an
        empty string) should also trigger the redetect attempt."""
        profile = GameProfile(gmod_enabled=True, gmod_dll_path="C:/does/not/exist/gMod.dll")
        with patch.object(gw1_launch.mod_root, "find_dll_under_mod_root", return_value="C:/found/gMod.dll") as mock_detect:
            result = _resolve_gmod_launch_decision(profile, gmod_injection_enabled=True, log=self.log)
        self.assertTrue(result)
        mock_detect.assert_called_once()
        self.assertEqual(profile.gmod_dll_path, "C:/found/gMod.dll")


class Py4GwHardFailRegressionTest(unittest.TestCase):
    """RELAY 091 explicitly scoped gMod-only -- confirms the identical
    py4gw_dll_path check just above it is genuinely untouched, not just
    read-and-assumed unchanged."""

    def test_py4gw_path_missing_still_hard_fails_before_any_process_created(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            fake_exe = f.name
        try:
            profile = GameProfile(
                executable_path=fake_exe,
                py4gw_enabled=True,
                py4gw_dll_path="C:/does/not/exist/Py4GW.dll",
                gmod_enabled=False,
            )
            result = launch_py4gw_profile(profile, py4gw_injection_enabled=True, gmod_injection_enabled=True)
        finally:
            Path(fake_exe).unlink()

        self.assertFalse(result.success)
        self.assertIn("py4gw_dll_path not found", result.error or "")


if __name__ == "__main__":
    unittest.main()
