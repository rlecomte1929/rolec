"""WS2 Task 2.3 — bulk latest compliance report per assignment (window pick).

Uses AuditMixin on an isolated in-memory SQLite engine so the root conftest
MagicMock of backend.database is not involved.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from backend.db.audit import AuditMixin


class _AuditDb(AuditMixin):
    def __init__(self, engine) -> None:
        self.engine = engine


def _fresh() -> _AuditDb:
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db = _AuditDb(eng)
    with eng.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE compliance_reports ("
                "id TEXT PRIMARY KEY, assignment_id TEXT NOT NULL, "
                "report_json TEXT NOT NULL, created_at TEXT NOT NULL)"
            )
        )
    return db


def _insert(db: _AuditDb, assignment_id: str, overall: str, created_at: str) -> None:
    with db.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO compliance_reports (id, assignment_id, report_json, created_at) "
                "VALUES (:id, :aid, :rj, :ca)"
            ),
            {
                "id": str(uuid.uuid4()),
                "aid": assignment_id,
                "rj": json.dumps({"overallStatus": overall}),
                "ca": created_at,
            },
        )


def test_get_latest_compliance_reports_by_assignment_ids_picks_latest_per_assignment():
    db = _fresh()
    a1 = f"asg-bulk-{uuid.uuid4().hex[:8]}"
    a2 = f"asg-bulk-{uuid.uuid4().hex[:8]}"
    t0 = datetime(2026, 1, 1, 0, 0, 0)
    _insert(db, a1, "NON_COMPLIANT", t0.isoformat())
    _insert(db, a1, "COMPLIANT", (t0 + timedelta(hours=2)).isoformat())
    _insert(db, a2, "NEEDS_REVIEW", (t0 + timedelta(hours=1)).isoformat())

    out = db.get_latest_compliance_reports_by_assignment_ids([a1, a2, "asg-missing", a1])
    assert set(out) == {a1, a2}
    assert out[a1]["overallStatus"] == "COMPLIANT"
    assert out[a2]["overallStatus"] == "NEEDS_REVIEW"


def test_get_latest_compliance_reports_by_assignment_ids_empty():
    db = _fresh()
    assert db.get_latest_compliance_reports_by_assignment_ids([]) == {}
    assert db.get_latest_compliance_reports_by_assignment_ids(None) == {}
