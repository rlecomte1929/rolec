"""
Unit tests for scripts/check_deliverable_integrity.py (HYGIENE-1).

Pure-Python, no network: exercises the path-extraction parser and the
check_tasks logic with synthetic Done-task records. The regression fixtures
prove the guard WOULD have caught the C1-04a / P3-01c leaks (a Done task whose
claimed file is not tracked) before they were fixed by hand.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# scripts/ is not a package — load the module directly by path.
_spec = importlib.util.spec_from_file_location(
    "check_deliverable_integrity",
    _REPO_ROOT / "scripts" / "check_deliverable_integrity.py",
)
cdi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cdi)


class ExtractDeliverablePathsTests(unittest.TestCase):
    def test_created_marker_with_backticks(self):
        text = "## Files changed\n- CREATED: `backend/app/services/factual_verifier.py` — purpose"
        self.assertEqual(
            cdi.extract_deliverable_paths(text),
            ["backend/app/services/factual_verifier.py"],
        )

    def test_created_marker_without_backticks(self):
        text = "CREATED: prompts/docs/classifier/v1.txt (777 lines)"
        self.assertEqual(
            cdi.extract_deliverable_paths(text),
            ["prompts/docs/classifier/v1.txt"],
        )

    def test_move_into_form(self):
        text = "Move eval_factual_consistency.py into backend/scripts/eval_factual_consistency.py in the repo."
        self.assertIn(
            "backend/scripts/eval_factual_consistency.py",
            cdi.extract_deliverable_paths(text),
        )

    def test_multiple_paths_deduped_and_ordered(self):
        text = (
            "CREATED: `backend/a.py`\n"
            "CREATED: `prompts/b.txt`\n"
            "see also backend/a.py again"
        )
        self.assertEqual(
            cdi.extract_deliverable_paths(text),
            ["backend/a.py", "prompts/b.txt"],
        )

    def test_trailing_punctuation_stripped(self):
        text = "wrote audit/eu_ai_act/risk_register_v1.md, then reviewed it."
        self.assertEqual(
            cdi.extract_deliverable_paths(text),
            ["audit/eu_ai_act/risk_register_v1.md"],
        )

    def test_no_path_returns_empty(self):
        self.assertEqual(cdi.extract_deliverable_paths("Pure research write-up, no files."), [])

    def test_prose_without_known_root_is_not_a_path(self):
        # "the cases domain" / a bare filename without a known root → not a path.
        self.assertEqual(cdi.extract_deliverable_paths("Refactored the cases.py domain logic."), [])

    def test_supabase_migration_path(self):
        text = "CREATED: supabase/migrations/20260605500000_rce_tenant_rls.sql"
        self.assertEqual(
            cdi.extract_deliverable_paths(text),
            ["supabase/migrations/20260605500000_rce_tenant_rls.sql"],
        )


class CheckTasksTests(unittest.TestCase):
    def setUp(self):
        self.tracked = {"backend/app/services/landed.py", "prompts/ok.txt"}

    def test_present_path_passes_missing_path_is_flagged(self):
        tasks = [
            {"aiq": "AIQ-1", "title": "Landed task", "url": "u1",
             "paths": ["backend/app/services/landed.py"]},
            {"aiq": "AIQ-2", "title": "Leaked task", "url": "u2",
             "paths": ["backend/scripts/never_landed.py"]},
        ]
        missing = cdi.check_tasks(tasks, self.tracked, allowlist=set())
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["aiq"], "AIQ-2")
        self.assertEqual(missing[0]["path"], "backend/scripts/never_landed.py")

    def test_would_have_caught_c1_04a_and_p3_01c(self):
        # The exact shape of the two real leaks fixed on 2026-06-04.
        tasks = [
            {"aiq": "AIQ-490", "title": "C1-04a classifier prompt", "url": "u",
             "paths": ["prompts/docs/classifier/v1.txt"]},
            {"aiq": "AIQ-709", "title": "P3-01c factual evaluator", "url": "u",
             "paths": ["backend/scripts/eval_factual_consistency.py"]},
        ]
        missing = cdi.check_tasks(tasks, tracked_files=set(), allowlist=set())
        self.assertEqual({m["aiq"] for m in missing}, {"AIQ-490", "AIQ-709"})

    def test_allowlist_suppresses_bare_path(self):
        tasks = [{"aiq": "AIQ-2", "title": "x", "url": "u",
                  "paths": ["backend/scripts/never_landed.py"]}]
        missing = cdi.check_tasks(
            tasks, self.tracked, allowlist={"backend/scripts/never_landed.py"}
        )
        self.assertEqual(missing, [])

    def test_allowlist_suppresses_aiq_scoped_key(self):
        tasks = [{"aiq": "AIQ-2", "title": "x", "url": "u",
                  "paths": ["backend/scripts/never_landed.py"]}]
        missing = cdi.check_tasks(
            tasks, self.tracked, allowlist={"AIQ-2:backend/scripts/never_landed.py"}
        )
        self.assertEqual(missing, [])


class LoadAllowlistTests(unittest.TestCase):
    def test_comment_aware(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "allow.txt"
            p.write_text(
                "# header comment\n"
                "\n"
                "backend/a.py  # renamed on commit\n"
                "AIQ-9:prompts/b.txt\n",
                encoding="utf-8",
            )
            self.assertEqual(
                cdi.load_allowlist(p),
                {"backend/a.py", "AIQ-9:prompts/b.txt"},
            )

    def test_missing_file_is_empty(self):
        self.assertEqual(cdi.load_allowlist(Path("/no/such/allowlist.txt")), set())


class UniqueIdTests(unittest.TestCase):
    def test_renders_prefix_and_number(self):
        prop = {"id": "zHIk", "type": "unique_id", "unique_id": {"prefix": "AIQ", "number": 775}}
        self.assertEqual(cdi._unique_id(prop), "AIQ-775")

    def test_number_only_when_no_prefix(self):
        self.assertEqual(cdi._unique_id({"unique_id": {"prefix": None, "number": 42}}), "42")

    def test_empty_when_absent(self):
        self.assertEqual(cdi._unique_id(None), "")
        self.assertEqual(cdi._unique_id({}), "")


if __name__ == "__main__":
    unittest.main()
