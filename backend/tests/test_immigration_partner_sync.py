"""
Unit tests for the immigration partner status-sync service (AIQ-379d).

Drives the AIQ-379c mock adapter end-to-end into an in-memory SQLite mirror of
``immigration_milestones`` + ``audit_logs``, and asserts:
  - first sync inserts every milestone and audits each one,
  - re-running is idempotent (no writes, no new audit rows),
  - a status transition produces exactly one audit row,
  - audit action_type is always insert/update (respects the CHECK constraint),
  - the rows are readable by the same query the HR timeline endpoint uses.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from backend.app.services.immigration_partner_adapter import (  # noqa: E402
    MilestoneStatus,
    MilestoneType,
)
from backend.app.services.immigration_partner_mock import MockPartnerAdapter  # noqa: E402
from backend.app.services.immigration_partner_sync import (  # noqa: E402
    apply_case_status,
    SyncResult,
)

_DDL = [
    """
    CREATE TABLE immigration_milestones (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL,
        org_id TEXT NOT NULL,
        milestone_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        sort_order INTEGER NOT NULL DEFAULT 0,
        target_date TEXT,
        completed_date TEXT,
        notes TEXT,
        evidence_url TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """,
    """
    CREATE TABLE audit_logs (
        id TEXT PRIMARY KEY,
        entity_type TEXT,
        entity_id TEXT,
        action_type TEXT,
        old_value_json TEXT,
        new_value_json TEXT,
        actor_type TEXT,
        actor_id TEXT
    )
    """,
]

CASE_ID = "case-abc-123"
ORG_ID = "org-xyz-789"


@pytest.fixture
def engine():
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        for stmt in _DDL:
            conn.execute(text(stmt))
    return eng


def _milestone_rows(engine):
    with engine.begin() as conn:
        return conn.execute(
            text("SELECT milestone_type, status FROM immigration_milestones WHERE case_id = :c"),
            {"c": CASE_ID},
        ).mappings().all()


def _audit_rows(engine):
    with engine.begin() as conn:
        return conn.execute(text("SELECT * FROM audit_logs")).mappings().all()


def _sync(engine, status):
    with engine.begin() as conn:
        return apply_case_status(conn, case_id=CASE_ID, org_id=ORG_ID, status=status)


def test_first_sync_inserts_and_audits_each_milestone(engine):
    status = MockPartnerAdapter().get_case_status("MOCK-CASE-REVIEW")
    res = _sync(engine, status)
    assert isinstance(res, SyncResult)
    assert res.created == len(status.milestones)
    assert res.updated == 0 and res.unchanged == 0
    assert res.audited == len(status.milestones)
    assert len(_milestone_rows(engine)) == len(status.milestones)
    assert len(_audit_rows(engine)) == len(status.milestones)


def test_rerun_is_idempotent(engine):
    status = MockPartnerAdapter().get_case_status("MOCK-CASE-REVIEW")
    _sync(engine, status)
    audits_after_first = len(_audit_rows(engine))

    res2 = _sync(engine, status)
    assert res2.created == 0
    assert res2.updated == 0
    assert res2.unchanged == len(status.milestones)
    assert res2.audited == 0
    # No duplicate milestones, no new audit rows.
    assert len(_milestone_rows(engine)) == len(status.milestones)
    assert len(_audit_rows(engine)) == audits_after_first


def test_status_transition_writes_one_audit_row(engine):
    adapter = MockPartnerAdapter()
    status = adapter.get_case_status("MOCK-CASE-EARLY")
    _sync(engine, status)
    audits_before = len(_audit_rows(engine))

    # Advance dossier_assembly from in_progress -> completed.
    advanced = adapter.get_case_status("MOCK-CASE-EARLY")
    for m in advanced.milestones:
        if m.milestone_type is MilestoneType.DOSSIER_ASSEMBLY:
            m.status = MilestoneStatus.COMPLETED

    res = _sync(engine, advanced)
    assert res.updated == 1
    assert res.audited == 1  # exactly one transition audited
    assert len(_audit_rows(engine)) == audits_before + 1

    rows = {r["milestone_type"]: r["status"] for r in _milestone_rows(engine)}
    assert rows["dossier_assembly"] == "completed"


def test_audit_action_type_respects_check_constraint(engine):
    status = MockPartnerAdapter().get_case_status("MOCK-CASE-GRANTED")
    _sync(engine, status)
    action_types = {r["action_type"] for r in _audit_rows(engine)}
    assert action_types <= {"insert", "update", "delete"}
    # Semantic event lives in new_value_json, not action_type.
    assert all("partner_milestone" in (r["new_value_json"] or "") for r in _audit_rows(engine))


def test_synced_rows_visible_to_timeline_query(engine):
    # Mirrors the SELECT used by GET /api/hr/cases/{case_id}/immigration/milestones.
    status = MockPartnerAdapter().get_case_status("MOCK-CASE-GRANTED")
    _sync(engine, status)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT milestone_type, status, evidence_url
                FROM immigration_milestones
                WHERE case_id = :case_id
                ORDER BY sort_order ASC, created_at ASC
                """
            ),
            {"case_id": CASE_ID},
        ).mappings().all()
    assert [r["milestone_type"] for r in rows] == [
        "application_filed",
        "visa_decision",
        "visa_issued",
    ]
    # Evidence URL carried through for the granted visa.
    visa = next(r for r in rows if r["milestone_type"] == "visa_issued")
    assert visa["evidence_url"].endswith("visa.pdf")
