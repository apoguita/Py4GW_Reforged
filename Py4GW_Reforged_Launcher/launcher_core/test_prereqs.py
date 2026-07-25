"""Unit tests for launcher_core/prereqs.py's VC++ 14.x check (RELAY 088).

No committed test coverage existed for prereqs.py at all before this --
verified via a direct search (find -iname "*test*") rather than assumed, since
RELAY 088's own testing instruction ("extend existing prereq tests") turned
out to be based on a premise that didn't hold. Writing real coverage here
instead of just the manual on-machine check the entry also asked for, since
mocking winreg is safe (no risk of touching/uninstalling anything on a real
machine to exercise the "not found" branch) and this is exactly the kind of
registry-parsing logic that's easy to silently break later.

Run: .venv\\Scripts\\python.exe -m unittest launcher_core.test_prereqs -v
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from launcher_core import prereqs


class FakeWinregModule:
    """Minimal stand-in for the winreg module, driven by a dict of
    {(hive, subkey): {value_name: value}} for OpenKey/QueryValueEx, and a
    dict of {(hive, subkey): [(display_name, display_version), ...]} for the
    Uninstall-scan EnumKey/QueryValueEx path. Missing keys raise
    FileNotFoundError, matching the real winreg module's behavior."""

    KEY_READ = 0x20019
    KEY_WOW64_32KEY = 0x0200
    KEY_WOW64_64KEY = 0x0100
    HKEY_LOCAL_MACHINE = object()

    def __init__(self, runtimes_keys=None, uninstall_entries=None):
        self._runtimes_keys = runtimes_keys or {}
        self._uninstall_entries = uninstall_entries or {}

    def OpenKey(self, hive, subkey, *_args, **_kwargs):
        # Runtimes-key path: subkey ends in a real value dict.
        if subkey in self._runtimes_keys:
            return ("runtimes", subkey)
        # Uninstall-scan path: subkey is one of the two Uninstall roots.
        if subkey in self._uninstall_entries:
            return ("uninstall", subkey)
        raise FileNotFoundError(subkey)

    def QueryValueEx(self, key_handle, name):
        kind, subkey = key_handle
        if kind == "runtimes":
            values = self._runtimes_keys[subkey]
            if name not in values:
                raise FileNotFoundError(name)
            return values[name], 1
        # Uninstall entry sub-key: key_handle here is actually the specific
        # entry sub-key handle produced by EnumKey+OpenKey below.
        entry = key_handle
        if entry[0] != "entry":
            raise FileNotFoundError(name)
        display_name, display_version = entry[1]
        if name == "DisplayName":
            return display_name, 1
        if name == "DisplayVersion":
            return display_version, 1
        raise FileNotFoundError(name)

    def EnumKey(self, key_handle, index):
        kind, subkey = key_handle
        entries = self._uninstall_entries.get(subkey, [])
        if index >= len(entries):
            raise OSError("no more items")
        return f"entry_{index}"

    def CloseKey(self, _key_handle):
        pass

    # OpenKey is called twice per Uninstall entry in the real code path
    # (once for the root, once per enumerated sub-key) -- route the second
    # call (sub-key open) to the right fake "entry" handle.
    def _open_entry(self, subkey, subkey_name):
        entries = self._uninstall_entries.get(subkey, [])
        idx = int(subkey_name.rsplit("_", 1)[1])
        return ("entry", entries[idx])


def _make_fake_winreg(runtimes_keys=None, uninstall_entries=None):
    fake = FakeWinregModule(runtimes_keys=runtimes_keys, uninstall_entries=uninstall_entries)

    real_open_key = fake.OpenKey

    def open_key(hive_or_parent, subkey, *args, **kwargs):
        # The real code's second OpenKey call per Uninstall entry passes the
        # already-opened root's own key handle as the first arg (not a real
        # HKEY constant) plus the short enumerated sub-key name -- route
        # that to _open_entry instead of the root-level lookup.
        if isinstance(hive_or_parent, tuple) and hive_or_parent[0] == "uninstall":
            return fake._open_entry(hive_or_parent[1], subkey)
        return real_open_key(hive_or_parent, subkey, *args, **kwargs)

    fake.OpenKey = open_key
    return fake


class CheckVcRedist14PrereqTests(unittest.TestCase):
    def test_runtimes_key_found_both_archs(self):
        """Both Runtimes keys present -- the common/expected case."""
        fake = _make_fake_winreg(
            runtimes_keys={
                r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x86": {"Version": "v14.51.36247.00"},
                r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64": {"Version": "v14.51.36247.00"},
            },
        )
        with patch.object(prereqs, "winreg", fake):
            result = prereqs.check_vcredist14_prereq()
        self.assertEqual(result.x86_status, prereqs.VcRedistStatus.OK)
        self.assertEqual(result.x64_status, prereqs.VcRedistStatus.OK)
        self.assertEqual(result.x86_version, "v14.51.36247.00")
        self.assertEqual(result.x64_version, "v14.51.36247.00")
        self.assertTrue(result.is_ok)

    def test_runtimes_key_missing_falls_back_to_uninstall_scan(self):
        """Hypothetical/precedent-based scenario, not one actually observed
        on this project's own dev machine (there, both archs' Runtimes keys
        resolved fine once queried with the correct explicit WOW64 view --
        an earlier ad-hoc check without that view flag falsely suggested
        x86 was missing, corrected before landing this). Still worth
        covering: the 2013 check's own docstring documents Microsoft VC++
        redistributable *updates* leaving the Runtimes key stale/deleted
        while the software remains installed, and this fallback exists for
        the same reason -- verify it actually works, not just that it's
        present."""
        fake = _make_fake_winreg(
            runtimes_keys={
                r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64": {"Version": "v14.51.36247.00"},
            },
            uninstall_entries={
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall": [
                    ("Microsoft Visual C++ v14 Redistributable (x86) - 14.51.36247", "14.51.36247.0"),
                ],
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall": [],
            },
        )
        with patch.object(prereqs, "winreg", fake):
            result = prereqs.check_vcredist14_prereq()
        self.assertEqual(result.x86_status, prereqs.VcRedistStatus.OK)
        self.assertEqual(result.x86_version, "14.51.36247.0")
        self.assertEqual(result.x64_status, prereqs.VcRedistStatus.OK)

    def test_neither_present_reports_not_found(self):
        fake = _make_fake_winreg()
        with patch.object(prereqs, "winreg", fake):
            result = prereqs.check_vcredist14_prereq()
        self.assertEqual(result.x86_status, prereqs.VcRedistStatus.NOT_FOUND)
        self.assertEqual(result.x64_status, prereqs.VcRedistStatus.NOT_FOUND)
        self.assertFalse(result.is_ok)
        self.assertIsNone(result.x86_version)
        self.assertIsNone(result.x64_version)

    def test_uninstall_scan_marker_is_case_insensitive_and_matches_real_wording(self):
        """The marker string was corrected against this project's own real
        machine (RELAY 088) -- "v14 Redistributable", not the initially
        assumed "2015-2022 Redistributable". Confirms the real observed
        display-name format actually matches."""
        fake = _make_fake_winreg(
            uninstall_entries={
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall": [
                    ("MICROSOFT VISUAL C++ V14 REDISTRIBUTABLE (X64) - 14.51.36247", "14.51.36247.0"),
                ],
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall": [],
            },
        )
        with patch.object(prereqs, "winreg", fake):
            result = prereqs.check_vcredist14_prereq()
        self.assertEqual(result.x64_status, prereqs.VcRedistStatus.OK)

    def test_urls_are_the_unified_14x_line_not_2013(self):
        """Guards against ever accidentally pointing the 14.x install
        button at the 2013 URLs (or vice versa) -- the two constants must
        stay distinct."""
        self.assertNotEqual(prereqs.VCREDIST_14_X86_URL, prereqs.VCREDIST_2013_X86_URL)
        self.assertNotEqual(prereqs.VCREDIST_14_X64_URL, prereqs.VCREDIST_2013_X64_URL)
        self.assertIn("vc_redist.x86.exe", prereqs.VCREDIST_14_X86_URL)
        self.assertIn("vc_redist.x64.exe", prereqs.VCREDIST_14_X64_URL)


if __name__ == "__main__":
    unittest.main()
