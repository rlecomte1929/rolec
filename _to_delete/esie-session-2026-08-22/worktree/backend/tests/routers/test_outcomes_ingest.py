"""P1-07d / AIQ-687 — POST /api/internal/outcomes/ingest.

Idempotent, admin-only trigger over outcome_extractor. In-memory SQLite with a
StaticPool so the DB persists across the endpoint's SessionLocal() calls; consent
is granted via the OUTCOME_EXTRACTION_ENABLED flag (consent_records absent here).
"""
from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import models
from backend.app.auth_deps import require_admin
import backend.app.routers.outcomes_ingest as ingest

ADMIN = {"id": "a", "role": "ADMIN", "is_admin": True, "email": "a@x.com"}
NON_ADMIN = {"id": "e", "role": "EMPLOYEE", "is_admin": False, "email": "e@x.com"}


def _add_case(db, case_id="case-1", *, status="approved"):
    db.add(models.Case(
        id=case_id, draft_json=json.dumps({}), flags_json=json.dumps({}),
        status=status, origin_country="FRA", dest_country="NOR", purpose="long_stay_visa",
    ))
    db.commit()


class IngestEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        models.Case.__table__.create(bind=self.engine)
        models.CaseOutcome.__table__.create(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self._p = mock.patch.object(ingest, "SessionLocal", self.Session)
        self._p.start()
        os.environ["OUTCOME_EXTRACTION_ENABLED"] = "1"  # consent via flag

    def tearDown(self) -> None:
        self._p.stop()
        os.environ.pop("OUTCOME_EXTRACTION_ENABLED", None)

    def _count(self) -> int:
        with self.Session() as s:
            return s.query(models.CaseOutcome).count()

    # --- the task's criterion: idempotency ---------------------------------
    def test_double_call_writes_one_row(self):
        with self.Session() as s:
            _add_case(s, "case-1")
        ingest.ingest_outcome(ingest.IngestBody(case_id="case-1"), ADMIN)
        ingest.ingest_outcome(ingest.IngestBody(case_id="case-1"), ADMIN)
        self.assertEqual(self._count(), 1)

    def test_returns_ingested_true(self):
        with self.Session() as s:
            _add_case(s, "c2")
        res = ingest.ingest_outcome(ingest.IngestBody(case_id="c2"), ADMIN)
        self.assertEqual(res, {"case_id": "c2", "ingested": True})

    def test_unknown_case_404(self):
        with self.assertRaises(HTTPException) as ctx:
            ingest.ingest_outcome(ingest.IngestBody(case_id="nope"), ADMIN)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_no_consent_skips_no_row(self):
        os.environ.pop("OUTCOME_EXTRACTION_ENABLED", None)  # flag off → fail-closed
        with self.Session() as s:
            _add_case(s, "c3")
        res = ingest.ingest_outcome(ingest.IngestBody(case_id="c3"), ADMIN)
        self.assertFalse(res["ingested"])
        self.assertEqual(self._count(), 0)

    # --- auth: service-role/admin only -------------------------------------
    def test_require_admin_rejects_non_admin(self):
        with self.assertRaises(HTTPException) as ctx:
            require_admin(NON_ADMIN)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_require_admin_allows_admin(self):
        self.assertEqual(require_admin(ADMIN), ADMIN)


if __name__ == "__main__":
    unittest.main()
