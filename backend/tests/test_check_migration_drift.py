"""
Tests for scripts/check_migration_drift.py (AIQ-756-PREVENT) — the pure diff core,
no DB. Exercises the real functions against synthetic version sets + a temp
migrations dir.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "check_migration_drift", _REPO_ROOT / "scripts" / "check_migration_drift.py"
)
cmd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cmd)


class RepoVersionsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _touch(self, name: str):
        (self.dir / name).write_text("-- x", encoding="utf-8")

    def test_extracts_version_prefixes_and_ignores_non_migrations(self):
        self._touch("20260608100000_ingest_us_fr.sql")
        self._touch("20260608110000_ingest_uk_fr.sql")
        self._touch("README.md")            # ignored
        self._touch("not_a_migration.sql")  # no 14-digit prefix → ignored
        self.assertEqual(cmd.repo_versions(self.dir),
                         {"20260608100000", "20260608110000"})

    def test_versions_by_name_maps_name_to_version(self):
        self._touch("20260608100000_ingest_us_fr.sql")
        self.assertEqual(cmd.repo_versions_by_name(self.dir),
                         {"ingest_us_fr": "20260608100000"})

    def test_missing_dir_is_empty(self):
        self.assertEqual(cmd.repo_versions(self.dir / "nope"), set())


class FindDriftTests(unittest.TestCase):
    def test_no_drift_when_all_applied_have_repo_files(self):
        applied = {"20260608100000": "a", "20260608110000": "b"}
        repo = {"20260608100000", "20260608110000", "20260609000000"}  # repo-ahead is fine
        self.assertEqual(cmd.find_drift(applied, repo), [])

    def test_flags_prod_versions_with_no_repo_file(self):
        applied = {
            "20260604140233": "ingest_us_fr",   # drift: apply-time version
            "20260608110000": "ingest_uk_fr",   # has repo file
        }
        repo = {"20260608100000", "20260608110000"}
        drift = cmd.find_drift(applied, repo)
        self.assertEqual([d["version"] for d in drift], ["20260604140233"])
        self.assertEqual(drift[0]["name"], "ingest_us_fr")

    def test_repo_ahead_only_is_not_drift(self):
        # repo has versions not yet applied to prod — undeployed work, NOT an error
        applied = {"20260601000000": "x"}
        repo = {"20260601000000", "20260699000000"}
        self.assertEqual(cmd.find_drift(applied, repo), [])

    def test_output_is_sorted_by_version(self):
        applied = {"20260604153503": "z", "20260604140233": "a"}
        repo: set = set()
        self.assertEqual([d["version"] for d in cmd.find_drift(applied, repo)],
                         ["20260604140233", "20260604153503"])


if __name__ == "__main__":
    unittest.main()
