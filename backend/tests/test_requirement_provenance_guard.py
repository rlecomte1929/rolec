"""`scripts/check_requirement_provenance.py` encodes one invariant: a requirement we
SERVE (review_status='approved') must carry a citation.

These tests exercise `evaluate()` directly — the pure split of the guard — so the
behaviour is pinned without a database. The point is discrimination in BOTH directions:
a guard that flags everything gets switched off, and a guard that flags nothing is
decoration. See scripts/requirement_provenance_baseline.txt for the frozen 2026-08-20 debt.
"""
import importlib.util
import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CHECKER_PATH = os.path.join(_REPO_ROOT, "scripts", "check_requirement_provenance.py")

# Loaded by path: pytest does not collect scripts/ as a package.
_spec = importlib.util.spec_from_file_location("check_requirement_provenance", _CHECKER_PATH)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

BASELINE_ID = "e1d0a1c0-0001-5000-8000-000000000001"   # GERMANY — Employment letter
OTHER_BASELINE_ID = "893b7866-15bb-4d25-8830-a8027724b8b4"  # SINGAPORE — Employment letter


class TestEvaluate:
    def test_flags_a_new_served_uncited_row(self):
        """The whole point: a NEW uncited row that is being served must fail."""
        rows = [("new-id-0001", "PORTUGAL", "NIF registration")]
        new, _ = guard.evaluate(rows, {BASELINE_ID})
        assert [r[0] for r in new] == ["new-id-0001"]

    def test_does_not_flag_a_baseline_row(self):
        """Pre-existing debt must not fail the build, or nobody can merge anything."""
        rows = [(BASELINE_ID, "GERMANY", "Employment letter")]
        new, _ = guard.evaluate(rows, {BASELINE_ID})
        assert new == []

    def test_reports_a_baseline_row_that_was_fixed(self):
        """A fixed row should be prunable, so the baseline cannot rot into an amnesty."""
        rows = []
        new, now_clean = guard.evaluate(rows, {BASELINE_ID, OTHER_BASELINE_ID})
        assert new == []
        assert now_clean == sorted([BASELINE_ID, OTHER_BASELINE_ID])

    def test_mixed_new_and_baseline(self):
        rows = [
            (BASELINE_ID, "GERMANY", "Employment letter"),
            ("new-id-0002", "SPAIN", "Empadronamiento"),
        ]
        new, now_clean = guard.evaluate(rows, {BASELINE_ID, OTHER_BASELINE_ID})
        assert [r[0] for r in new] == ["new-id-0002"]
        assert now_clean == [OTHER_BASELINE_ID]

    def test_clean_database_passes(self):
        new, now_clean = guard.evaluate([], set())
        assert new == [] and now_clean == []


class TestBaselineFile:
    def test_baseline_parses_and_is_the_frozen_29(self):
        ids = guard.load_baseline()
        assert len(ids) == 29, "baseline should hold the 29 rows measured on prod 2026-08-20"
        assert BASELINE_ID in ids

    def test_baseline_ignores_comments_and_blanks(self, tmp_path):
        p = tmp_path / "b.txt"
        p.write_text("# a comment\n\nabc-123  # trailing note\n", encoding="utf-8")
        assert guard.load_baseline(str(p)) == {"abc-123"}


class TestQueryShape:
    def test_only_targets_served_rows(self):
        """A pending row with no citation is CORRECT — demoting must remain a valid fix."""
        sql = guard.VIOLATION_SQL.lower()
        assert "review_status = 'approved'" in sql
        assert "citations_json is null" in sql

    def test_does_not_constrain_citation_format(self):
        """Three formats coexist and all resolve; demanding one would flag 24 good rows."""
        sql = guard.VIOLATION_SQL.lower()
        assert "http" not in sql
        assert "verification_status" not in sql
