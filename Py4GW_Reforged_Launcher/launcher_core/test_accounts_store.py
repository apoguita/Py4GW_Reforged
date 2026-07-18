"""Unit tests for launcher_core/accounts_store.py (RELAY 066).

No committed test coverage existed for the old profile_store.py this
replaces, or for legacy_import.py -- every prior RELAY entry touching this
area (034, 060, 061) verified live instead. Writing real, checked-in
coverage here since accounts_store.py is now the single, permanent, only
data store this app has (no fallback), and carries real security-relevant
behavior (encrypt-on-first-touch, never round-tripping a plaintext
password) worth protecting against regression.

Run: .venv\\Scripts\\python.exe -m unittest launcher_core.test_accounts_store -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from launcher_core import accounts_store
from launcher_core.profile import GameProfile
from launcher_core.team import Team

_GIT_AVAILABLE = shutil.which("git") is not None

_SAMPLE_ACCOUNTS = {
    "Test Team 1": [
        {
            "character_name": "Test Char 1",
            "email": "test1@fake.com",
            "password": "hunter2",
            "gw_client_name": "Test 1",
            "gw_path": "C:/Games/Guild Wars 1/Client 00/Gw.exe",
            "extra_args": "-steam",
            "run_as_admin": True,
            "inject_py4gw": True,
            "inject_gmod": True,
            "gmod_mods": ["C:/mods/one.tpf"],
            "script_path": "testautorun.py",
            "enable_client_rename": True,
            "last_launch_time": None,
            "top_left": [0, 0],
            "width": 800,
            "height": 600,
        }
    ],
    "Test Team 2": [
        {
            "character_name": "Test Char 2",
            "email": "test2@fake.com",
            "password": "swordfish",
            "gw_path": "C:/Games/Guild Wars 1/Client 01/Gw.exe",
            "inject_py4gw": True,
            "inject_gmod": False,
        },
    ],
}


class TestBasicRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "accounts.json"
        self.path.write_text(json.dumps(_SAMPLE_ACCOUNTS), encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_loads_expected_profiles_and_teams(self):
        profiles = accounts_store.load_profiles(self.path)
        teams = accounts_store.load_teams(self.path)
        self.assertEqual(len(profiles), 2)
        self.assertEqual(sorted(t.name for t in teams), ["Test Team 1", "Test Team 2"])

    def test_character_name_maps_to_both_name_fields(self):
        profiles = accounts_store.load_profiles(self.path)
        p1 = next(p for p in profiles if p.character_name == "Test Char 1")
        self.assertEqual(p1.name, "Test Char 1")
        self.assertEqual(p1.executable_path, "C:/Games/Guild Wars 1/Client 00/Gw.exe")
        self.assertTrue(p1.py4gw_enabled)
        self.assertTrue(p1.gmod_enabled)
        self.assertEqual(p1.gmod_plugin_paths, ["C:/mods/one.tpf"])

    def test_password_encrypted_on_first_load_not_left_plaintext(self):
        profiles = accounts_store.load_profiles(self.path)
        p1 = next(p for p in profiles if p.character_name == "Test Char 1")
        self.assertTrue(p1.password_protected)
        self.assertNotEqual(p1.password_protected, "hunter2")

    def test_save_drops_plaintext_password_keeps_protected(self):
        profiles = accounts_store.load_profiles(self.path)
        accounts_store.save_profiles(profiles, self.path)
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        tc1 = raw["Test Team 1"][0]
        self.assertNotIn("password", tc1)
        self.assertIn("password_protected", tc1)
        self.assertTrue(tc1["password_protected"])

    def test_save_preserves_unknown_legacy_fields(self):
        profiles = accounts_store.load_profiles(self.path)
        accounts_store.save_profiles(profiles, self.path)
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        tc1 = raw["Test Team 1"][0]
        self.assertEqual(tc1.get("gw_client_name"), "Test 1")
        self.assertEqual(tc1.get("run_as_admin"), True)
        self.assertIn("last_launch_time", tc1)
        self.assertIn("top_left", tc1)

    def test_save_adds_new_owned_fields(self):
        profiles = accounts_store.load_profiles(self.path)
        accounts_store.save_profiles(profiles, self.path)
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        tc1 = raw["Test Team 1"][0]
        self.assertIn("id", tc1)
        self.assertIn("name", tc1)

    def test_ids_stable_across_reload(self):
        profiles = accounts_store.load_profiles(self.path)
        ids_before = {p.character_name: p.id for p in profiles}
        accounts_store.save_profiles(profiles, self.path)

        profiles2 = accounts_store.load_profiles(self.path)
        ids_after = {p.character_name: p.id for p in profiles2}
        self.assertEqual(ids_before, ids_after)


class TestMultiTeamWriteBack(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "accounts.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_profile_in_two_teams_gets_two_identical_copies(self):
        t1 = Team(id="Alpha", name="Alpha")
        t2 = Team(id="Beta", name="Beta")
        p1 = GameProfile(character_name="Dual Member", email="dual@fake.com", team_ids=["Alpha", "Beta"])

        accounts_store.save_teams([t1, t2], self.path)
        accounts_store.save_profiles([p1], self.path)

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        alpha_copy = next(a for a in raw["Alpha"] if a["character_name"] == "Dual Member")
        beta_copy = next(a for a in raw["Beta"] if a["character_name"] == "Dual Member")
        self.assertEqual(alpha_copy, beta_copy)
        self.assertEqual(alpha_copy["id"], p1.id)

    def test_copies_stay_in_sync_after_a_field_change(self):
        t1 = Team(id="Alpha", name="Alpha")
        t2 = Team(id="Beta", name="Beta")
        p1 = GameProfile(character_name="Dual Member", email="dual@fake.com", team_ids=["Alpha", "Beta"])
        accounts_store.save_teams([t1, t2], self.path)
        accounts_store.save_profiles([p1], self.path)

        profiles = accounts_store.load_profiles(self.path)
        target = next(p for p in profiles if p.character_name == "Dual Member")
        target.email = "changed@fake.com"
        accounts_store.save_profiles(profiles, self.path)

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        alpha_copy = next(a for a in raw["Alpha"] if a["character_name"] == "Dual Member")
        beta_copy = next(a for a in raw["Beta"] if a["character_name"] == "Dual Member")
        self.assertEqual(alpha_copy, beta_copy)
        self.assertEqual(alpha_copy["email"], "changed@fake.com")

    def test_zero_team_profile_lands_in_unassigned_bucket_not_lost(self):
        p1 = GameProfile(character_name="No Team Yet", team_ids=[])
        accounts_store.save_profiles([p1], self.path)

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        all_accounts = [a for accounts in raw.values() for a in accounts]
        self.assertEqual(len(all_accounts), 1)
        self.assertEqual(all_accounts[0]["character_name"], "No Team Yet")

    def test_unassigned_bucket_never_exposed_as_a_real_team(self):
        p1 = GameProfile(character_name="No Team Yet", team_ids=[])
        accounts_store.save_profiles([p1], self.path)

        teams = accounts_store.load_teams(self.path)
        self.assertEqual(teams, [])

    def test_reload_after_multiteam_save_round_trips_membership(self):
        t1 = Team(id="Alpha", name="Alpha")
        t2 = Team(id="Beta", name="Beta")
        p1 = GameProfile(character_name="Dual Member", team_ids=["Alpha", "Beta"])
        p2 = GameProfile(character_name="Solo Member", team_ids=["Alpha"])
        accounts_store.save_teams([t1, t2], self.path)
        accounts_store.save_profiles([p1, p2], self.path)

        profiles = accounts_store.load_profiles(self.path)
        by_name = {p.character_name: p for p in profiles}
        self.assertEqual(sorted(by_name["Dual Member"].team_ids), ["Alpha", "Beta"])
        self.assertEqual(by_name["Solo Member"].team_ids, ["Alpha"])


class TestSaveAccountsCombined(unittest.TestCase):
    """A new team AND a profile belonging to it, added in the same logical
    operation, saved via save_profiles()+save_teams() SEPARATELY -- the
    real bug self-caught during RELAY 066's own live verification of
    bridge.py's import_legacy_accounts. Each save call independently
    re-reads the OTHER half fresh from disk to preserve it, so whichever
    call runs first can't see the other's still-in-memory-only changes
    yet -- a brand-new team saved via save_teams() alone, followed by
    save_profiles() for a profile that belongs to it, works only by
    save-order luck; the reverse order silently drops the profile into
    the unassigned bucket. save_accounts() must not have this problem at
    all -- it writes both in one real call, no re-read involved.
    """

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "accounts.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_new_team_plus_its_member_both_land_correctly(self):
        team = Team(id="Brand New", name="Brand New")
        profile = GameProfile(character_name="Fresh Member", team_ids=["Brand New"])
        accounts_store.save_accounts([profile], [team], self.path)

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertIn("Brand New", raw)
        self.assertEqual([a["character_name"] for a in raw["Brand New"]], ["Fresh Member"])
        self.assertNotIn(accounts_store._UNASSIGNED_TEAM_KEY, raw)

    def test_separate_calls_in_the_broken_order_reproduces_the_bug(self):
        # Documents the failure mode this function exists to avoid --
        # save_profiles() first, save_teams() second, is the order that
        # actually breaks (the reverse order happens to work by luck).
        team = Team(id="Brand New", name="Brand New")
        profile = GameProfile(character_name="Fresh Member", team_ids=["Brand New"])

        accounts_store.save_profiles([profile], self.path)
        accounts_store.save_teams([team], self.path)

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        unassigned = raw.get(accounts_store._UNASSIGNED_TEAM_KEY, [])
        self.assertEqual(
            [a["character_name"] for a in unassigned],
            ["Fresh Member"],
            "documents the known-broken separate-calls order -- save_accounts() avoids this",
        )


class TestDuplicateDedup(unittest.TestCase):
    """A real account appearing under two team keys, on a first-ever load
    with no ids yet -- the actual RELAY 060/061 bug this store must not
    reintroduce."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "accounts.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_same_account_across_two_teams_merges_not_duplicates(self):
        account = {
            "character_name": "Shared Char",
            "email": "shared@fake.com",
            "gw_path": "C:/Games/Guild Wars 1/Client 00/Gw.exe",
        }
        data = {"Class Team": [account], "Misc Team": [dict(account)]}
        self.path.write_text(json.dumps(data), encoding="utf-8")

        profiles = accounts_store.load_profiles(self.path)
        teams = accounts_store.load_teams(self.path)
        self.assertEqual(len(profiles), 1)
        self.assertEqual(sorted(profiles[0].team_ids), ["Class Team", "Misc Team"])
        self.assertEqual(sorted(t.name for t in teams), ["Class Team", "Misc Team"])

    def test_inconsistent_email_across_listings_still_merges(self):
        # RELAY 061's own real gap -- one listing has email, the other blank.
        with_email = {
            "character_name": "Shared Char",
            "email": "shared@fake.com",
            "gw_path": "C:/Games/Guild Wars 1/Client 00/Gw.exe",
        }
        without_email = {
            "character_name": "Shared Char",
            "email": "",
            "gw_path": "C:/Games/Guild Wars 1/Client 00/Gw.exe",
        }
        data = {"Team A": [with_email], "Team B": [without_email]}
        self.path.write_text(json.dumps(data), encoding="utf-8")

        profiles = accounts_store.load_profiles(self.path)
        self.assertEqual(len(profiles), 1)
        self.assertEqual(sorted(profiles[0].team_ids), ["Team A", "Team B"])


class TestMigration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.mod_root = Path(self.tmpdir.name)
        self.root_accounts = self.mod_root / "accounts.json"
        self.root_accounts.write_text(json.dumps(_SAMPLE_ACCOUNTS), encoding="utf-8")
        self._orig_resolve = accounts_store.mod_root.resolve_mod_repo_path
        accounts_store.mod_root.resolve_mod_repo_path = lambda: self.mod_root

    def tearDown(self):
        accounts_store.mod_root.resolve_mod_repo_path = self._orig_resolve
        self.tmpdir.cleanup()

    def test_first_load_migrates_from_root_file(self):
        new_path = accounts_store.default_accounts_path()
        self.assertFalse(new_path.exists())

        profiles = accounts_store.load_profiles()
        self.assertEqual(len(profiles), 2)
        self.assertTrue(new_path.exists())

    def test_root_file_never_modified(self):
        before = self.root_accounts.read_text(encoding="utf-8")
        accounts_store.load_profiles()
        after = self.root_accounts.read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def test_second_load_does_not_remigrate(self):
        accounts_store.load_profiles()
        new_path = accounts_store.default_accounts_path()
        mtime_1 = new_path.stat().st_mtime_ns

        accounts_store.load_profiles()
        mtime_2 = new_path.stat().st_mtime_ns
        self.assertEqual(mtime_1, mtime_2)

    def test_remigrates_if_new_file_deleted(self):
        accounts_store.load_profiles()
        new_path = accounts_store.default_accounts_path()
        new_path.unlink()
        self.assertFalse(new_path.exists())

        profiles = accounts_store.load_profiles()
        self.assertEqual(len(profiles), 2)
        self.assertTrue(new_path.exists())

    def test_no_migration_when_root_file_absent(self):
        self.root_accounts.unlink()
        profiles = accounts_store.load_profiles()
        self.assertEqual(profiles, [])
        self.assertFalse(accounts_store.default_accounts_path().exists())


@unittest.skipUnless(_GIT_AVAILABLE, "git not on PATH")
class TestGitTrackingCheck(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        subprocess.run(["git", "init", "-q"], cwd=self.repo_root, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.repo_root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo_root, check=True)
        self.accounts_path = self.repo_root / "Settings" / "Py4GW_Reforged_Launcher" / "accounts.json"
        self.accounts_path.parent.mkdir(parents=True)
        self.accounts_path.write_text("{}", encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_untracked_file_reads_false(self):
        self.assertFalse(accounts_store.is_accounts_file_tracked(self.accounts_path))

    def test_tracked_file_reads_true(self):
        subprocess.run(
            ["git", "add", "Settings/Py4GW_Reforged_Launcher/accounts.json"], cwd=self.repo_root, check=True
        )
        subprocess.run(["git", "commit", "-q", "-m", "test"], cwd=self.repo_root, check=True)
        self.assertTrue(accounts_store.is_accounts_file_tracked(self.accounts_path))

    def test_no_git_repo_at_all_reads_false_not_error(self):
        no_git_dir = Path(tempfile.mkdtemp())
        try:
            path = no_git_dir / "accounts.json"
            path.write_text("{}", encoding="utf-8")
            self.assertFalse(accounts_store.is_accounts_file_tracked(path))
        finally:
            shutil.rmtree(no_git_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
