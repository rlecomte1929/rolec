"""
Tests for scripts/check_migration_drift.py (AIQ-756-PREVENT) — the pure diff core,
no DB. Exercises the real functions against synthetic version sets + a temp
migrations dir.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_files_by_version_maps_version_to_name(self):
        self._touch("20260608100000_ingest_us_fr.sql")
        self._touch("README.md")            # ignored
        self._touch("not_a_migration.sql")  # no 14-digit prefix → ignored
        self.assertEqual(cmd.repo_files_by_version(self.dir),
                         {"20260608100000": "ingest_us_fr"})

    def test_missing_dir_is_empty(self):
        self.assertEqual(cmd.repo_versions(self.dir / "nope"), set())
        self.assertEqual(cmd.repo_files_by_version(self.dir / "nope"), {})


class FindRepoOnlyTests(unittest.TestCase):
    """Direction B (warning): repo files with no matching prod row."""

    def test_no_repo_only_when_all_repo_files_applied(self):
        applied = {"20260608100000": "a", "20260608110000": "b"}
        repo_by_ver = {"20260608100000": "a", "20260608110000": "b"}
        self.assertEqual(cmd.find_repo_only(applied, repo_by_ver), [])

    def test_flags_repo_files_with_no_prod_row(self):
        # repo file 20260699000000 has never been applied → Direction B warning
        applied = {"20260608100000": "a"}
        repo_by_ver = {"20260608100000": "a", "20260699000000": "future_work"}
        repo_only = cmd.find_repo_only(applied, repo_by_ver)
        self.assertEqual([d["version"] for d in repo_only], ["20260699000000"])
        self.assertEqual(repo_only[0]["name"], "future_work")

    def test_prod_ahead_is_not_repo_only(self):
        # prod has a version the repo lacks — that's Direction A, NOT Direction B
        applied = {"20260601000000": "x", "20260604140233": "drifted"}
        repo_by_ver = {"20260601000000": "x"}
        self.assertEqual(cmd.find_repo_only(applied, repo_by_ver), [])

    def test_output_is_sorted_by_version(self):
        applied: dict = {}
        repo_by_ver = {"20260604153503": "z", "20260604140233": "a"}
        self.assertEqual([d["version"] for d in cmd.find_repo_only(applied, repo_by_ver)],
                         ["20260604140233", "20260604153503"])


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


class MainCliTests(unittest.TestCase):
    """End-to-end main() behaviour: exit codes + always-printed summary line."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _touch(self, name: str):
        (self.dir / name).write_text("-- x", encoding="utf-8")

    def _run(self, applied: dict) -> tuple[int, str]:
        """Run main() with a stubbed DB + temp migrations dir; return (exit_code, stdout)."""
        buf = io.StringIO()
        with mock.patch.dict("os.environ", {"DATABASE_URL": "postgresql://stub"}), \
             mock.patch.object(cmd, "MIGRATIONS_DIR", self.dir), \
             mock.patch.object(cmd, "query_applied_versions", return_value=applied), \
             mock.patch("sys.argv", ["check_migration_drift.py"]), \
             contextlib.redirect_stdout(buf):
            code = cmd.main()
        return code, buf.getvalue()

    def test_clean_ledger_exits_0_with_summary(self):
        self._touch("20260608100000_a.sql")
        code, out = self._run({"20260608100000": "a"})
        self.assertEqual(code, 0)
        self.assertIn("Migration ledger:", out)
        self.assertIn("0 mismatch(es)", out)

    def test_prod_row_with_no_repo_file_exits_1(self):
        # Direction A: prod has a version the repo lacks → hard failure
        self._touch("20260608100000_a.sql")
        code, out = self._run({"20260608100000": "a", "20260604140233": "ghost"})
        self.assertEqual(code, 1)
        self.assertIn("FAILED", out)
        self.assertIn("Migration ledger:", out)  # summary still printed

    def test_repo_file_with_no_prod_row_exits_0_with_warn(self):
        # Direction B: repo file never applied → WARNING, exit 0
        self._touch("20260608100000_a.sql")
        self._touch("20260699000000_future_work.sql")
        code, out = self._run({"20260608100000": "a"})
        self.assertEqual(code, 0)
        self.assertIn("WARN", out)
        self.assertIn("20260699000000_future_work.sql", out)
        self.assertIn("Migration ledger:", out)  # summary always printed


if __name__ == "__main__":
    unittest.main()
