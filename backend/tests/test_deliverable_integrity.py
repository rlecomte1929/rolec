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

    def test_move_into_prose_is_not_a_claim(self):
        # Reviewer-steps prose ("move X into <path>") is NOT a CREATED:/MODIFIED:
        # claim — this is the dominant false-positive class from the first live
        # run (the file landed at a different path than the prose suggested).
        text = "Move eval_factual_consistency.py into backend/scripts/eval_factual_consistency.py in the repo."
        self.assertEqual(cdi.extract_deliverable_paths(text), [])

    def test_modified_marker_is_a_claim(self):
        text = "- MODIFIED: `backend/main.py` — registered the router"
        self.assertEqual(cdi.extract_deliverable_paths(text), ["backend/main.py"])

    def test_deleted_marker_is_not_a_claim(self):
        # A retirement task's deliverable is the file's ABSENCE. Counting it as a
        # claim reports "Done but NOT in the repo" for a task that did its job.
        text = "- DELETED: `frontend/src/pages/admin/mission-control/WorkBoard.tsx`"
        self.assertEqual(cdi.extract_deliverable_paths(text), [])

    def test_deleted_bullet_inside_files_changed_section(self):
        # The real AIQ-1565 shape that broke the guard repo-wide: DELETED bullets
        # sit under the same "## Files changed" heading as their MODIFIED siblings,
        # so the section rule alone would claim them. The MODIFIED path must still
        # be claimed — this must not become a blanket escape hatch.
        text = (
            "## Files changed\n"
            "- MODIFIED: frontend/src/pages/admin/AdminFeedback.tsx — removed the toggle\n"
            "- DELETED: frontend/src/pages/admin/mission-control/WorkBoard.tsx\n"
            "- DELETED: frontend/src/pages/admin/mission-control/WorkBoard.test.tsx\n"
        )
        self.assertEqual(
            cdi.extract_deliverable_paths(text),
            ["frontend/src/pages/admin/AdminFeedback.tsx"],
        )

    def test_removed_marker_is_not_a_claim(self):
        text = "## Files changed\n- REMOVED: `backend/app/routers/legacy.py`"
        self.assertEqual(cdi.extract_deliverable_paths(text), [])

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
        text = "CREATED: audit/eu_ai_act/risk_register_v1.md, then reviewed it."
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

    def test_what_was_built_section_numbered_bullets(self):
        # The Cowork phantom pattern (AI-003 cluster): deliverables listed as
        # numbered bullets under "## What was built" with NO CREATED: marker.
        text = (
            "## What was built\n\n"
            "Three deliverables closing the Tier-3 gaps:\n\n"
            "1. outputs/ai-003d_iso_42001_gap_analysis.md — walk of all 7 clauses\n"
            "2. audit/eu_ai_act/article_14_self_assessment.md — self-assessment\n"
        )
        self.assertEqual(
            cdi.extract_deliverable_paths(text),
            [
                "outputs/ai-003d_iso_42001_gap_analysis.md",
                "audit/eu_ai_act/article_14_self_assessment.md",
            ],
        )

    def test_outputs_root_is_recognized(self):
        # outputs/ is a real deliverable root (productionised-spike / Cowork scratch).
        text = "CREATED: outputs/friday_005_policy_ingestion_spike.py"
        self.assertEqual(
            cdi.extract_deliverable_paths(text),
            ["outputs/friday_005_policy_ingestion_spike.py"],
        )

    def test_empty_basename_prose_capture_is_skipped(self):
        # Prose like "11 backend/db/.py mixins" must not yield "backend/db/.py"
        # (a basename that is just an extension is never a real deliverable).
        text = "## What was built\nThe monolith is now 11 backend/db/.py mixins.\n"
        self.assertEqual(cdi.extract_deliverable_paths(text), [])

    def test_non_claim_heading_closes_the_section(self):
        # A "Reviewer steps" heading is NOT a claim section — paths under it
        # (example commands / prose) must not be captured.
        text = (
            "## What was built\n"
            "1. outputs/real_deliverable.md — yes\n"
            "## Reviewer steps\n"
            "run `cat outputs/should_not_capture.md` to inspect\n"
        )
        self.assertEqual(
            cdi.extract_deliverable_paths(text),
            ["outputs/real_deliverable.md"],
        )


class CheckTasksTests(unittest.TestCase):
    def setUp(self):
        self.tracked = {"backend/app/services/landed.py", "prompts/ok.txt"}

    # These four pass `ever_added=None` (the default), i.e. no git history. That is
    # deliberate: with no history the guard keeps its original present-tense semantics
    # and an absent path is still `missing`, so these fixtures keep asserting exactly
    # what they always did. The history-aware behaviour is covered separately in
    # backend/tests/test_notion_guards_measure_something.py.
    def test_present_path_passes_missing_path_is_flagged(self):
        tasks = [
            {"aiq": "AIQ-1", "title": "Landed task", "url": "u1",
             "paths": ["backend/app/services/landed.py"]},
            {"aiq": "AIQ-2", "title": "Leaked task", "url": "u2",
             "paths": ["backend/scripts/never_landed.py"]},
        ]
        missing, _moved, _mangled = cdi.check_tasks(tasks, self.tracked, allowlist=set())
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
        missing, _moved, _mangled = cdi.check_tasks(
            tasks, tracked_files=set(), allowlist=set())
        self.assertEqual({m["aiq"] for m in missing}, {"AIQ-490", "AIQ-709"})

    def test_allowlist_suppresses_bare_path(self):
        tasks = [{"aiq": "AIQ-2", "title": "x", "url": "u",
                  "paths": ["backend/scripts/never_landed.py"]}]
        missing, _moved, _mangled = cdi.check_tasks(
            tasks, self.tracked, allowlist={"backend/scripts/never_landed.py"}
        )
        self.assertEqual(missing, [])

    def test_allowlist_suppresses_aiq_scoped_key(self):
        tasks = [{"aiq": "AIQ-2", "title": "x", "url": "u",
                  "paths": ["backend/scripts/never_landed.py"]}]
        missing, _moved, _mangled = cdi.check_tasks(
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


class HistoryScanTests(unittest.TestCase):
    """The ever-existed check is the difference between a stale path and a phantom.

    Measured 2026-08-23: the guard reported 110 missing deliverables, of which 71 had been added
    on a branch in this repo's own history — `backend/app/routers/hr_rfq.py` among them, added
    2026-05-18 and deleted 2026-07-22. `is_shallow()` saw nothing wrong because the clone was not
    shallow; `git log --all` simply matched no refs on a detached-HEAD CI checkout and returned
    the empty set.
    """

    def test_history_is_complete_rejects_an_empty_scan(self):
        self.assertFalse(cdi.history_is_complete(set(), {"backend/app/main.py"}))

    def test_history_is_complete_rejects_a_partial_scan(self):
        """The exact invariant: a file in the working tree was added by some commit."""
        self.assertFalse(
            cdi.history_is_complete({"a.py"}, {"a.py", "b.py"}))

    def test_history_is_complete_accepts_a_superset(self):
        """Deleted paths legitimately appear in history and not in the tree."""
        self.assertTrue(
            cdi.history_is_complete({"a.py", "b.py", "gone.py"}, {"a.py", "b.py"}))


class RestampedMigrationTests(unittest.TestCase):
    """A migration re-stamped to clear a timestamp collision is the same migration."""

    TRACKED = {
        "supabase/migrations/20261013000000_test_drive_tester_contact.sql",
        "supabase/migrations/20260521070001_completion_pct_trigger.sql",
    }

    def test_resolves_the_same_migration_under_a_later_timestamp(self):
        self.assertEqual(
            cdi.resolve_restamped_migration(
                "supabase/migrations/20260927000000_test_drive_tester_contact.sql", self.TRACKED),
            "supabase/migrations/20261013000000_test_drive_tester_contact.sql")

    def test_refuses_when_two_migrations_share_a_name(self):
        """Ambiguity gets no resolution rather than an arbitrary one."""
        tracked = self.TRACKED | {
            "supabase/migrations/20261099000000_test_drive_tester_contact.sql"}
        self.assertIsNone(cdi.resolve_restamped_migration(
            "supabase/migrations/20260927000000_test_drive_tester_contact.sql", tracked))

    def test_a_migration_that_never_existed_is_not_resolved(self):
        self.assertIsNone(cdi.resolve_restamped_migration(
            "supabase/migrations/20260101000000_never_written.sql", self.TRACKED))

    def test_only_applies_to_migrations(self):
        self.assertIsNone(cdi.resolve_restamped_migration(
            "backend/app/routers/hr_rfq.py", {"backend/app/routers/hr_rfq.py"}))


class PathSuffixResolutionTests(unittest.TestCase):
    """A note written one directory out names a file that is really here."""

    TRACKED = {
        "backend/app/services/ai_trace_logger.py",
        "backend/scripts/rag_eval_harness.py",
        "README.md",
        "backend/README.md",
        "frontend/README.md",
    }

    def test_resolves_a_wrong_prefix(self):
        self.assertEqual(
            cdi.resolve_by_path_suffix("backend/services/ai_trace_logger.py", self.TRACKED),
            "backend/app/services/ai_trace_logger.py")
        self.assertEqual(
            cdi.resolve_by_path_suffix("scripts/rag_eval_harness.py", self.TRACKED),
            "backend/scripts/rag_eval_harness.py")

    def test_a_bare_filename_never_resolves(self):
        """`README.md` exists in dozens of directories; one segment is not evidence."""
        self.assertIsNone(cdi.resolve_by_path_suffix("docs/README.md", self.TRACKED))

    def test_an_ambiguous_tail_is_refused(self):
        tracked = {"a/x/thing.py", "b/x/thing.py"}
        self.assertIsNone(cdi.resolve_by_path_suffix("c/x/thing.py", tracked))

    def test_a_path_that_is_nowhere_is_not_resolved(self):
        self.assertIsNone(cdi.resolve_by_path_suffix(
            "apps/hr-dashboard/src/features/resolution/CandidateCard.tsx", self.TRACKED))


class ResolversFeedTheMovedBucketTests(unittest.TestCase):
    """Resolved claims must not fail the build, and must say where the file went."""

    def test_a_restamped_migration_is_moved_not_missing(self):
        tracked = {"supabase/migrations/20261013000000_test_drive_tester_contact.sql"}
        tasks = [{"aiq": "1629", "title": "t", "url": "u", "paths": [
            "supabase/migrations/20260927000000_test_drive_tester_contact.sql"]}]
        missing, moved, _ = cdi.check_tasks(tasks, tracked, allowlist=set(), ever_added=set())
        self.assertEqual(missing, [])
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0]["resolved_to"], sorted(tracked)[0])
        self.assertIn("re-stamped", moved[0]["why"])

    def test_a_genuinely_absent_path_still_fails(self):
        """The guard must remain able to fail — the lesson of #2035."""
        tasks = [{"aiq": "9999", "title": "t", "url": "u",
                  "paths": ["backend/app/nowhere_at_all.py"]}]
        missing, moved, _ = cdi.check_tasks(
            tasks, {"backend/app/main.py"}, allowlist=set(), ever_added=set())
        self.assertEqual(len(missing), 1)
        self.assertEqual(moved, [])
