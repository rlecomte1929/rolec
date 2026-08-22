"""Executing a beam import, and verifying afterwards that it held.

`plan_import` decides; these are the two functions that WRITE and that CHECK. A recording
connection stands in for the database so "a dry run writes nothing" can be asserted as the
absence of any write statement rather than as a row count that happened to stay the same —
the two look identical in a passing test and only one of them is the guarantee.

The freeze tests matter more than they look. An item at `imported` already produced a
staging row under a specific country and pillar. Re-pointing it silently would orphan that
row in `otto_staging` with nothing referencing it, and `verify_import` would then happily
confirm a row that no longer matches what a human approved — a green check over a broken
audit trail.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import pytest

from backend.imports.candidate_beam.importer import (
    execute_import,
    expected_body,
    expected_dedupe_key,
    verify_import,
)


# ---------------------------------------------------------------------------
# Test doubles.
# ---------------------------------------------------------------------------


class _Result:
    """Enough of a SQLAlchemy Result for `stage()` and `verify_import()`."""

    def __init__(self, rows: Sequence[Any] = ()):
        self._rows = list(rows)

    def __iter__(self):
        return iter(self._rows)

    def scalar(self):
        return self._rows[0] if self._rows else None

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class RecordingConn:
    """Records every statement. Writes are what we assert the absence of."""

    def __init__(self, existing_keys: Sequence[str] = (), staged: Sequence[Dict[str, Any]] = ()):
        self.executed: List[str] = []
        self._existing = [(k,) for k in existing_keys]
        self._staged = list(staged)

    def execute(self, stmt, params=None):
        sql = " ".join(str(stmt).split())
        self.executed.append(sql)
        upper = sql.upper()
        if "SELECT DEDUPE_KEY FROM OTTO_STAGING" in upper:
            return _Result(self._existing)
        if "FROM OTTO_STAGING.IMMIGRATION_FACT_CANDIDATES" in upper and "SELECT" in upper:
            return _Result(self._staged)
        return _Result([1])

    @property
    def writes(self) -> List[str]:
        return [
            s for s in self.executed
            if s.upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]


def candidate(**over) -> Dict[str, Any]:
    base = {
        "candidate_uid": "cb-1",
        "title": "PPSN registration",
        "status": "approved",
        "official_guidance": "Apply at an Intreo centre.",
        "actual_reality": "Appointments run six weeks out in Dublin.",
        "action_required": "Employee books the appointment in week one.",
        "source": "gov.ie",
        "category": "registration",
        "flagged": False,
    }
    base.update(over)
    return base


BATCH = "beam-FR-NO-001"


# ---------------------------------------------------------------------------
# Dry run.
# ---------------------------------------------------------------------------


def test_a_dry_run_issues_no_write_statement_at_all():
    """THE guarantee. Not 'the counts did not change' — no write was attempted."""
    conn = RecordingConn()
    result = execute_import(
        conn,
        run_id="run-1",
        candidates=[candidate()],
        country="IE",
        batch_id=BATCH,
        imported_by="admin@relopass.com",
        dry_run=True,
    )
    assert result.dry_run is True
    assert conn.writes == []
    assert result.stamped == 0


def test_a_dry_run_still_reports_what_would_be_staged():
    """A preview whose numbers differ from the real run is worse than no preview."""
    conn = RecordingConn()
    result = execute_import(
        conn, run_id="run-1", candidates=[candidate()], country="IE", batch_id=BATCH,
        imported_by="a@b.c", dry_run=True,
    )
    assert result.staged == 1


def test_a_real_run_stages_and_then_stamps_the_audit_columns():
    conn = RecordingConn()
    result = execute_import(
        conn, run_id="run-1", candidates=[candidate()], country="IE", batch_id=BATCH,
        imported_by="admin@relopass.com", dry_run=False,
    )
    assert result.staged == 1
    assert result.stamped == 1
    assert any("CANDIDATE_BEAM_ITEMS" in w.upper() for w in conn.writes)
    assert any("OTTO_STAGING.IMMIGRATION_FACT_CANDIDATES" in w.upper() for w in conn.writes)


def test_the_import_never_promotes():
    """`promote()` writes public.requirement_items, which is customer-facing. Beam output
    stops at staging and reaches a customer only through /admin/countries."""
    conn = RecordingConn()
    execute_import(
        conn, run_id="run-1", candidates=[candidate()], country="IE", batch_id=BATCH,
        imported_by="a@b.c", dry_run=False,
    )
    assert not any("REQUIREMENT_ITEMS" in w.upper() for w in conn.writes)


# ---------------------------------------------------------------------------
# Freeze.
# ---------------------------------------------------------------------------


def test_reimport_changing_the_country_is_refused_with_a_reason():
    conn = RecordingConn()
    result = execute_import(
        conn,
        run_id="run-1",
        candidates=[candidate(status="imported", import_country="IE", import_requirement_type="IDENTITY")],
        country="FR",
        batch_id=BATCH,
        imported_by="a@b.c",
        dry_run=False,
    )
    assert result.ok is False
    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert conflict.field == "country"
    assert conflict.already == "IE" and conflict.requested == "FR"
    assert "refusing to change" in conflict.reason
    assert conn.writes == [], "a refused import must not half-apply"


def test_reimport_changing_the_pillar_is_refused():
    conn = RecordingConn()
    result = execute_import(
        conn,
        run_id="run-1",
        candidates=[
            candidate(
                status="imported", import_country="IE",
                import_requirement_type="RESIDENCE", category="registration",
            )
        ],
        country="IE",
        batch_id=BATCH,
        imported_by="a@b.c",
        pillar_overrides={"cb-1": "IDENTITY"},
        dry_run=False,
    )
    assert result.ok is False
    assert result.conflicts[0].field == "pillar"
    assert conn.writes == []


def test_reimporting_an_unchanged_item_is_a_no_op_not_an_error():
    """An operator re-running a partly-failed batch should not have to hand-pick the rows
    that already went through."""
    conn = RecordingConn()
    result = execute_import(
        conn,
        run_id="run-1",
        candidates=[
            candidate(status="imported", import_country="IE", import_requirement_type="IDENTITY")
        ],
        country="IE",
        batch_id=BATCH,
        imported_by="a@b.c",
        pillar_overrides={"cb-1": "IDENTITY"},
        dry_run=False,
    )
    assert result.ok is True
    assert result.conflicts == []
    assert [s.reason for s in result.skipped] == ["already imported"]


def test_a_conflict_aborts_the_whole_batch():
    """Importing around a refused instruction half-applies something the operator would
    reasonably read as atomic."""
    conn = RecordingConn()
    result = execute_import(
        conn,
        run_id="run-1",
        candidates=[
            candidate(candidate_uid="cb-1"),
            candidate(
                candidate_uid="cb-2", status="imported",
                import_country="IE", import_requirement_type="IDENTITY",
            ),
        ],
        country="FR",
        batch_id=BATCH,
        imported_by="a@b.c",
        dry_run=False,
    )
    assert result.ok is False
    assert result.staged == 0
    assert conn.writes == []


@pytest.mark.parametrize("status", ["pending_review", "rejected", "verified", "approved_and_served", ""])
def test_only_approved_candidates_are_ever_staged(status):
    """The verdict whitelist. `verified` is not a state this system has — the schema CHECK
    refuses it — and nothing here may route around the human gate."""
    conn = RecordingConn()
    result = execute_import(
        conn, run_id="run-1", candidates=[candidate(status=status)], country="IE",
        batch_id=BATCH, imported_by="a@b.c", dry_run=False,
    )
    assert result.staged == 0
    assert conn.writes == []


# ---------------------------------------------------------------------------
# Verify.
# ---------------------------------------------------------------------------


def _imported_item(**over) -> Dict[str, Any]:
    item = candidate(status="imported", import_country="IE", import_requirement_type="IDENTITY")
    item.update(over)
    return item


def _staged_row_for(item: Dict[str, Any], **over) -> Dict[str, Any]:
    row = {
        "dedupe_key": expected_dedupe_key(item),
        "fact_text": expected_body(item),
        "destination_country": item["import_country"],
        "pillar": item["import_requirement_type"],
        "beam_uid": item["candidate_uid"],
    }
    row.update(over)
    return row


def test_verify_passes_when_the_staging_row_is_intact():
    item = _imported_item()
    conn = RecordingConn(staged=[_staged_row_for(item)])
    report = verify_import(conn, run_id="run-1", imported_items=[item])
    assert report.ok is True
    assert (report.checked, report.intact) == (1, 1)
    assert conn.writes == [], "verify is read-only"


def test_verify_detects_a_deleted_staging_row():
    item = _imported_item()
    conn = RecordingConn(staged=[])
    report = verify_import(conn, run_id="run-1", imported_items=[item])
    assert report.ok is False
    assert report.findings[0].problem == "missing"


def test_verify_detects_a_mangled_staging_row():
    """The deliberate-tamper case: someone edited the text a human approved."""
    item = _imported_item()
    conn = RecordingConn(staged=[_staged_row_for(item, fact_text="something else entirely")])
    report = verify_import(conn, run_id="run-1", imported_items=[item])
    assert report.ok is False
    assert report.findings[0].problem == "content_drift"


def test_verify_detects_a_row_refiled_under_a_different_pillar():
    item = _imported_item()
    conn = RecordingConn(staged=[_staged_row_for(item, pillar="HOUSING")])
    report = verify_import(conn, run_id="run-1", imported_items=[item])
    assert report.ok is False
    assert report.findings[0].problem == "pillar_drift"
    assert "HOUSING" in report.findings[0].detail


def test_verify_reports_the_approved_backlog():
    """Approved-but-not-imported is not a fault — it is the operator's remaining work, and
    a verify that omitted it would read as 'everything is done'."""
    report = verify_import(
        RecordingConn(staged=[]), run_id="run-1", imported_items=[], approved_not_imported=7
    )
    assert report.ok is True
    assert report.approved_not_imported == 7


def test_the_expected_key_is_recomputed_not_read_back():
    """A verify that read back the key the importer stored would confirm its own
    arithmetic and miss the row being edited underneath it."""
    assert expected_dedupe_key(
        {"import_country": "IE", "title": "PPSN registration", "import_requirement_type": "IDENTITY"}
    ) == "IE|ppsn_registration|identity"
