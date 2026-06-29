"""P1-07c / AIQ-686 — outcome-sharing consent endpoint + gate.

SQLite-backed, prod-shaped consent_records + case_assignments. Calls the router
handlers directly (no DATABASE_URL at import) and exercises the
``has_outcome_consent`` gate over the same engine.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import backend.app.routers.outcome_consent as oc
from backend.app.services import outcome_extractor

SCHEMA = """
CREATE TABLE consent_records (
  id TEXT PRIMARY KEY, employee_id TEXT, case_id TEXT, purpose TEXT,
  consented INTEGER, consent_version TEXT, consent_text_hash TEXT,
  consented_at TEXT, withdrawn_at TEXT, withdrawn_reason TEXT,
  ip_address TEXT, user_agent TEXT, created_at TEXT
);
CREATE TABLE case_assignments (
  id TEXT PRIMARY KEY, case_id TEXT, employee_user_id TEXT
);
"""

CASE_ID = "case-1"
EMP_ID = "emp-1"
EMPLOYEE = {"id": EMP_ID, "role": "EMPLOYEE", "email": "e@x.com", "auth_uuid": EMP_ID}
OTHER = {"id": "emp-2", "role": "EMPLOYEE", "email": "o@x.com", "auth_uuid": "emp-2"}


def _req():
    return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"),
                           headers={"user-agent": "pytest"})


class OutcomeConsentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        with self.engine.begin() as c:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    c.execute(text(stmt))
            c.execute(text(
                "INSERT INTO case_assignments (id, case_id, employee_user_id) "
                "VALUES ('a1', :cid, :emp)"), {"cid": CASE_ID, "emp": EMP_ID})
        self._p = mock.patch.object(oc.db, "engine", self.engine)
        self._p.start()
        self._p2 = mock.patch.object(
            oc.db, "get_assignment_by_case_id",
            lambda case_id, *a, **k: {"employee_user_id": EMP_ID} if case_id == CASE_ID else None)
        self._p2.start()
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self) -> None:
        self._p.stop(); self._p2.stop()

    def _gate(self) -> bool:
        with self.Session() as s:
            return outcome_extractor.has_outcome_consent(s, CASE_ID)

    # --- gate ---------------------------------------------------------------
    def test_gate_denies_without_consent_and_flag_off(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("OUTCOME_EXTRACTION_ENABLED", None)
            self.assertFalse(self._gate())

    def test_optin_then_gate_allows(self):
        res = oc.set_outcome_consent(CASE_ID, oc.OutcomeConsentBody(consented=True), _req(), EMPLOYEE)
        self.assertEqual(res["consented"], True)
        self.assertTrue(self._gate())
        self.assertEqual(oc.get_outcome_consent(CASE_ID, EMPLOYEE)["consented"], True)

    def test_withdraw_flips_gate_off(self):
        oc.set_outcome_consent(CASE_ID, oc.OutcomeConsentBody(consented=True), _req(), EMPLOYEE)
        self.assertTrue(self._gate())
        oc.set_outcome_consent(CASE_ID, oc.OutcomeConsentBody(consented=False), _req(), EMPLOYEE)
        self.assertFalse(self._gate())
        self.assertEqual(oc.get_outcome_consent(CASE_ID, EMPLOYEE)["consented"], False)

    # --- tenant scoping -----------------------------------------------------
    def test_other_employee_cannot_set(self):
        with self.assertRaises(HTTPException) as ctx:
            oc.set_outcome_consent(CASE_ID, oc.OutcomeConsentBody(consented=True), _req(), OTHER)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_other_employee_cannot_read(self):
        with self.assertRaises(HTTPException) as ctx:
            oc.get_outcome_consent(CASE_ID, OTHER)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_unknown_case_404(self):
        with self.assertRaises(HTTPException) as ctx:
            oc.set_outcome_consent("nope", oc.OutcomeConsentBody(consented=True), _req(), EMPLOYEE)
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
