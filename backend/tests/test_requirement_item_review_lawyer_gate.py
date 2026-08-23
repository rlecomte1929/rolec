"""[AIQ-2046] The requirement_items half of the lawyer-review gate — where it actually bit.

`requirement_facts` has 0 flagged rows, so the gate there is preventive. THIS table is where
4 flagged rows are already approved and served: all IRELAND / RESIDENCE on the ES->IE
corridor, approved 2026-08-21 12:02:59 UTC in a single scripted call covering 9 rows at one
identical microsecond. Nothing warned, because `review_country_requirement` validated exactly
two things — that the status string is approved/rejected, and that country_code matches the
path — and never looked at `citations_json`, which is where the flag lives (there is no
column for it).

The handler is called directly rather than through TestClient: the suite's conftest replaces
`backend.database` with a MagicMock, so a TestClient test would assert against mock return
values and pass while proving nothing.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import datetime
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app import models  # noqa: E402
from backend.app.routers import admin  # noqa: E402

ADMIN = {"id": "admin-1", "email": "admin@relopass.com"}

# Verbatim from production row 04c9ba47-8c41-5b28-9012-4a10393cfb45 in shape: the flag is
# nested INSIDE a citation object, not at the top level.
FLAGGED_CITES = json.dumps([{
    "url": "https://www.citizensinformation.ie/en/moving-country/visas-for-ireland/",
    "topic_key": "spanish_residence_does_not_grant_irish_entry",
    "name": "Citizens Information — Visa requirements",
    "needs_lawyer_review": True,
}])
CLEAN_CITES = json.dumps([{
    "url": "https://www.irishimmigration.ie/x", "name": "ISD", "needs_lawyer_review": False,
}])


class _Body:
    def __init__(self, status):
        self.status = status


class RequirementItemLawyerGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        models.RequirementItem.__table__.create(self.engine)
        Session = sessionmaker(bind=self.engine)
        patcher = mock.patch.object(admin, "SessionLocal", Session)
        patcher.start()
        self.addCleanup(patcher.stop)

        # list_sources / the audit sink are not what this test is about.
        self.addCleanup(mock.patch.object(
            admin.crud, "list_sources", lambda *a, **k: []).stop)
        mock.patch.object(admin.crud, "list_sources", lambda *a, **k: []).start()
        self.addCleanup(mock.patch.object(admin, "_audit_postgres", lambda **k: None).stop)
        mock.patch.object(admin, "_audit_postgres", lambda **k: None).start()

        with Session() as s:
            for rid, cites, attest in (
                ("flagged", FLAGGED_CITES, None),
                ("flagged-attested", FLAGGED_CITES, "attested"),
                ("flagged-requested", FLAGGED_CITES, "requested"),
                ("clean", CLEAN_CITES, None),
            ):
                s.add(models.RequirementItem(
                    id=rid, country_code="IRELAND", purpose="work", pillar="RESIDENCE",
                    title=f"Ireland — {rid}", description="d", severity="required",
                    owner="employee", review_status="pending", required_fields_json="[]",
                    citations_json=cites, attestation_status=attest,
                    last_verified_at=datetime.utcnow(),
                ))
            s.commit()

    def _review(self, rid, status="approved"):
        return admin.review_country_requirement("IRELAND", rid, _Body(status), user=ADMIN)

    def _stored(self, rid):
        Session = sessionmaker(bind=self.engine)
        with Session() as s:
            return s.get(models.RequirementItem, rid).review_status

    # ── the gate ──────────────────────────────────────────────────────────────

    def test_approving_a_flagged_requirement_is_refused(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self._review("flagged")
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("needs_lawyer_review", str(ctx.exception.detail))
        self.assertEqual(self._stored("flagged"), "pending", "a refused approval must not land")

    def test_the_flag_is_found_nested_inside_a_citation_object(self) -> None:
        """The production shape. A gate reading only a top-level key would pass this row
        straight through — which is exactly how the 4 live rows got approved."""
        self.assertNotIn('"needs_lawyer_review": true', FLAGGED_CITES.split("[")[0])
        with self.assertRaises(HTTPException):
            self._review("flagged")

    def test_a_counsel_attestation_discharges_the_flag(self) -> None:
        """The gate must have an exit, or a flagged claim is frozen forever."""
        self._review("flagged-attested")
        self.assertEqual(self._stored("flagged-attested"), "approved")

    def test_merely_REQUESTING_attestation_is_not_sign_off(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self._review("flagged-requested")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_an_unflagged_requirement_still_approves(self) -> None:
        self._review("clean")
        self.assertEqual(self._stored("clean"), "approved")

    def test_a_flagged_requirement_can_still_be_REJECTED(self) -> None:
        """Gating a claim's EXIT would trap the rows most in need of removal."""
        self._review("flagged", status="rejected")
        self.assertEqual(self._stored("flagged"), "rejected")


if __name__ == "__main__":
    unittest.main()
