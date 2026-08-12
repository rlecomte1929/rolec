"""Unit tests for the canonical_case_id drift tripwire (AIQ-1731).

The gate exists so AIQ-1731 (cleanup) and AIQ-1732 (UNIQUE constraint) can stay
deferred safely: the frozen known-bad stock is baselined, and only NEW violations
fail CI. Pure stdlib + tmp files — no DB.

Mirrors scripts/tests/test_check_rls_coverage.py, including a self-guard so the
check cannot pass by parsing nothing.
"""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_canonical_case_id_drift as ccd  # noqa: E402


def _write(tmp_path, text):
    p = tmp_path / "canonical_case_id_baseline.txt"
    p.write_text(text)
    return p


# --------------------------------------------------------------------------
# baseline parsing
# --------------------------------------------------------------------------

def test_missing_file_is_empty_baseline(tmp_path):
    assert ccd.load_baseline(tmp_path / "nope.txt") == set()


def test_comments_and_blanks_are_ignored(tmp_path):
    p = _write(tmp_path, "# header\n\nabc-1\n\n# --- null (1) ---\ndef-2\n")
    assert ccd.load_baseline(p) == {"abc-1", "def-2"}


def test_inline_comment_after_an_id_is_stripped(tmp_path):
    p = _write(tmp_path, "abc-1  # dangling, seed artifact\n")
    assert ccd.load_baseline(p) == {"abc-1"}


# --------------------------------------------------------------------------
# the fail path — this is what the gate is for
# --------------------------------------------------------------------------

def test_new_bad_row_is_a_violation():
    live = [("brand-new", "duplicate")]
    assert ccd.new_violations(live, {"known-1"}) == [("brand-new", "duplicate")]


def test_baselined_row_is_not_a_violation():
    live = [("known-1", "null")]
    assert ccd.new_violations(live, {"known-1"}) == []


def test_baselined_row_that_changed_bucket_is_still_not_a_violation():
    """Keyed on the id alone: a baselined row moving between buckets is not NEW
    badness, and re-failing on it would make the gate noisy while cleanup is parked."""
    live = [("known-1", "dangling")]
    assert ccd.new_violations(live, {"known-1"}) == []


def test_only_the_new_rows_are_reported():
    live = [("known-1", "null"), ("new-1", "dangling"), ("new-2", "duplicate")]
    assert ccd.new_violations(live, {"known-1"}) == [
        ("new-1", "dangling"), ("new-2", "duplicate")
    ]


def test_clean_prod_passes():
    assert ccd.new_violations([], {"known-1"}) == []


def test_cleaned_up_row_is_reported_stale_not_failed():
    """After the deferred cleanup runs, baselined ids drop out of the live set.
    That must be a WARN (trim the baseline), never a failure."""
    assert ccd.stale_baseline_entries([], {"known-1", "known-2"}) == ["known-1", "known-2"]
    assert ccd.new_violations([], {"known-1", "known-2"}) == []


# --------------------------------------------------------------------------
# the committed baseline + query
# --------------------------------------------------------------------------

def test_repo_baseline_is_empty_after_the_pre_launch_reset():
    """AIQ-1737·3 executed the pre-launch canonical_case_id repair — prod is now 0 null /
    0 dangling / 0 duplicate — so the deferral baseline is EMPTY (regenerated via
    --update-baseline). SELF-GUARD: a truncated/missing file would ALSO parse to an empty
    set, so assert the header is intact (real regenerated file) AND that it holds zero ids.
    Any future NEW bad row is caught by the live-vs-baseline check, not by this file."""
    assert ccd.BASELINE_FILE.exists(), "baseline file is missing"
    text = ccd.BASELINE_FILE.read_text()
    assert "one assignment id per line" in text, "baseline header missing — file may be truncated"
    assert ccd.load_baseline(ccd.BASELINE_FILE) == set(), (
        "baseline should be empty after the AIQ-1737·3 repair; a non-empty file means "
        "either the repair regressed or the file was hand-edited"
    )


def test_audit_sql_covers_all_three_buckets():
    """SELF-GUARD: a query that silently stopped classifying one bucket would make
    the gate blind to that whole failure mode."""
    sql = ccd.AUDIT_SQL
    assert "'null'" in sql
    assert "'dangling'" in sql
    assert "'duplicate'" in sql
    # both case tables must be consulted, or every canonical reads as dangling
    assert "relocation_cases" in sql
    assert "public.cases" in sql
    # the bucket <> 'ok' filter is what keeps the result to offenders only
    assert "bucket <> 'ok'" in sql


def test_audit_sql_casts_uuid_to_text():
    """canonical_case_id is `text` while the id columns are `uuid`; an untyped
    comparison raises rather than returning rows."""
    assert "rc.id::text = ca.canonical_case_id::text" in ccd.AUDIT_SQL
    assert "c.id::text = ca.canonical_case_id::text" in ccd.AUDIT_SQL


# --------------------------------------------------------------------------
# exit codes
# --------------------------------------------------------------------------

def _stub_query(rows, watched=818):
    """Stand in for the DB call: (bad_rows, assignments_watched)."""
    return lambda _url: (rows, watched)


def test_main_exits_1_on_a_new_violation(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub")
    monkeypatch.setattr(ccd, "BASELINE_FILE", _write(tmp_path, "known-1\n"))
    monkeypatch.setattr(ccd, "query_bad_rows", _stub_query([("new-1", "duplicate")]))
    monkeypatch.setattr(sys, "argv", ["check_canonical_case_id_drift.py"])
    assert ccd.main() == 1


def test_main_exits_0_when_only_baselined_rows_are_bad(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub")
    monkeypatch.setattr(ccd, "BASELINE_FILE", _write(tmp_path, "known-1\n"))
    monkeypatch.setattr(ccd, "query_bad_rows", _stub_query([("known-1", "null")]))
    monkeypatch.setattr(sys, "argv", ["check_canonical_case_id_drift.py"])
    assert ccd.main() == 0


def test_main_exits_2_without_a_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(sys, "argv", ["check_canonical_case_id_drift.py"])
    assert ccd.main() == 2


# --------------------------------------------------------------------------
# A tripwire over an empty table proves nothing (2026-08-11 guard sweep)
# --------------------------------------------------------------------------
# AUDIT_SQL returns only offenders, so "0 bad rows" is identical output whether 818
# assignments are all clean or the table is empty. The baseline is now empty too, so the
# "every entry went stale at once" signal that used to hint at this is gone. And
# scripts/e2e_purge.py runs on every push to `main`, which makes an emptied table a live
# possibility rather than a thought experiment.


def test_empty_case_assignments_table_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub")
    monkeypatch.setattr(ccd, "BASELINE_FILE", _write(tmp_path, "# empty baseline\n"))
    monkeypatch.setattr(ccd, "query_bad_rows", _stub_query([], watched=0))
    monkeypatch.setattr(sys, "argv", ["check_canonical_case_id_drift.py"])
    assert ccd.main() == 1


def test_empty_table_fails_even_for_update_baseline(monkeypatch, tmp_path):
    """Regenerating from an empty table would write an empty baseline and read as a
    completed cleanup."""
    baseline = _write(tmp_path, "known-1\n")
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub")
    monkeypatch.setattr(ccd, "BASELINE_FILE", baseline)
    monkeypatch.setattr(ccd, "query_bad_rows", _stub_query([], watched=0))
    monkeypatch.setattr(
        sys, "argv", ["check_canonical_case_id_drift.py", "--update-baseline"]
    )
    assert ccd.main() == 1
    assert baseline.read_text() == "known-1\n", "must not have been rewritten"


def test_clean_populated_table_still_passes(monkeypatch, tmp_path):
    """The current prod shape: rows present, none bad, nothing baselined."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub")
    monkeypatch.setattr(ccd, "BASELINE_FILE", _write(tmp_path, "# empty baseline\n"))
    monkeypatch.setattr(ccd, "query_bad_rows", _stub_query([], watched=818))
    monkeypatch.setattr(sys, "argv", ["check_canonical_case_id_drift.py"])
    assert ccd.main() == 0


def test_json_reports_rows_watched(monkeypatch, tmp_path, capsys):
    import json

    monkeypatch.setenv("DATABASE_URL", "postgresql://stub")
    monkeypatch.setattr(ccd, "BASELINE_FILE", _write(tmp_path, "# empty baseline\n"))
    monkeypatch.setattr(ccd, "query_bad_rows", _stub_query([], watched=818))
    monkeypatch.setattr(sys, "argv", ["check_canonical_case_id_drift.py", "--json"])
    rc = ccd.main()
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["assignments_watched"] == 818
    assert payload["pass"] is True
