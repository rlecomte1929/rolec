"""Tests for identity_observability helpers and presence of identity_obs log lines."""
from __future__ import annotations

import json
import logging
import os
import sys
import unittest
import uuid
from datetime import datetime

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.database as dbmod
from backend.database import Database
from backend.dev_seed_auth import ensure_dev_seed_auth_user
from backend.identity_observability import (
    identity_event,
    principal_fingerprint,
    principal_fingerprint_from_login_identifier,
)
from backend.services.assignment_claim_link_service import reconcile_pending_assignment_claims
from backend.services.unified_assignment_creation import create_assignment_with_contact_and_invites


def _seed_company(db: Database, company_id: str, name: str = "Test Co") -> None:
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        conn.execute(
            text("INSERT INTO companies (id, name, created_at) VALUES (:id, :n, :ca)"),
            {"id": company_id, "n": name, "ca": now},
        )


class IdentityObservabilityUnitTests(unittest.TestCase):
    def test_principal_fingerprint_stable_and_no_raw_email_in_log(self):
        fp = principal_fingerprint("User@Example.COM", None)
        self.assertEqual(fp, principal_fingerprint("user@example.com", None))
        self.assertEqual(len(fp), 16)
        self.assertNotIn("example", fp.lower())
        self.assertTrue(all(c in "0123456789abcdef" for c in fp))

    def test_principal_fingerprint_username_branch(self):
        fp = principal_fingerprint(None, "My_User")
        self.assertEqual(len(fp), 16)

    def test_principal_fingerprint_from_login_identifier(self):
        self.assertEqual(
            principal_fingerprint_from_login_identifier("A@B.COM"),
            principal_fingerprint("a@b.com", None),
        )
        self.assertEqual(
            principal_fingerprint_from_login_identifier("alice"),
            principal_fingerprint(None, "alice"),
        )

    def test_identity_event_json_contains_event_and_omits_none(self):
        log_capture = logging.getLogger("backend.identity_observability")
        with self.assertLogs(log_capture, level="INFO") as cm:
            identity_event(
                "identity.test.fixture",
                request_id="rid-1",
                company_id="co-x",
                empty_should_drop=None,
                also_empty="",
            )
        self.assertEqual(len(cm.records), 1)
        msg = cm.records[0].getMessage()
        self.assertTrue(msg.startswith("identity_obs "))
        payload = json.loads(msg.split("identity_obs ", 1)[1])
        self.assertEqual(payload["event"], "identity.test.fixture")
        self.assertEqual(payload["request_id"], "rid-1")
        self.assertEqual(payload["company_id"], "co-x")
        self.assertNotIn("empty_should_drop", payload)


class DevSeedAuthTests(unittest.TestCase):
    def test_ensure_dev_seed_auth_user_is_idempotent_by_email(self):
        eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        prev_engine, prev_sqlite = dbmod._engine, dbmod._is_sqlite
        dbmod._engine = eng
        dbmod._is_sqlite = True
        try:
            db = Database()
            h = "x" * 60
            first = ensure_dev_seed_auth_user(
                db,
                user_id="seed-user-1",
                email="seed.dedupe@example.com",
                password_hash=h,
                role="EMPLOYEE",
                name="S",
            )
            second = ensure_dev_seed_auth_user(
                db,
                user_id="seed-user-2",
                email="seed.dedupe@example.com",
                password_hash=h,
                role="EMPLOYEE",
                name="T",
            )
            self.assertEqual(first, second)
        finally:
            dbmod._engine = prev_engine
            dbmod._is_sqlite = prev_sqlite


class IdentityObservabilityFlowTests(unittest.TestCase):
    """Assert key events appear during unified creation + reconcile (integration-style)."""

    def setUp(self):
        eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        self._prev_engine = dbmod._engine
        self._prev_sqlite = dbmod._is_sqlite
        dbmod._engine = eng
        dbmod._is_sqlite = True
        self.db = Database()

    def tearDown(self):
        dbmod._engine = self._prev_engine
        dbmod._is_sqlite = self._prev_sqlite

    def test_unified_creation_emits_assign_and_contact_events(self):
        db = self.db
        _seed_company(db, "co-obs-1")
        hr = "hr-obs-1"
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-obs-1")
        obs_log = logging.getLogger("backend.identity_observability")
        with self.assertLogs(obs_log, level="INFO") as cm:
            create_assignment_with_contact_and_invites(
                db,
                company_id="co-obs-1",
                hr_user_id=hr,
                case_id=case_id,
                employee_identifier_raw="flow.obs@example.com",
                employee_first_name=None,
                employee_last_name=None,
                employee_user_id=None,
                assignment_status="assigned",
                request_id="req-obs-1",
                observability_channel="hr",
            )
        joined = " ".join(r.getMessage() for r in cm.records)
        self.assertIn("identity.assign.created", joined)
        self.assertIn("identity.contact.resolve", joined)
        self.assertIn("identity.invite.pending_ensure", joined)
        self.assertIn('"channel":"hr"', joined)
        self.assertNotIn("flow.obs@example.com", joined)

    def test_reconcile_emits_complete_with_attachment(self):
        db = self.db
        _seed_company(db, "co-obs-2")
        hr = "hr-obs-2"
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-obs-2")
        email = "reconcile.obs@example.com"
        r = create_assignment_with_contact_and_invites(
            db,
            company_id="co-obs-2",
            hr_user_id=hr,
            case_id=case_id,
            employee_identifier_raw=email,
            employee_first_name=None,
            employee_last_name=None,
            employee_user_id=None,
            assignment_status="assigned",
            request_id=None,
        )
        uid = str(uuid.uuid4())
        self.assertTrue(db.create_user(uid, None, email, "h", "EMPLOYEE", "R"))
        obs_log = logging.getLogger("backend.identity_observability")
        with self.assertLogs(obs_log, level="INFO") as cm:
            reconcile_pending_assignment_claims(
                db,
                user_id=uid,
                email=email,
                username=None,
                role="EMPLOYEE",
                request_id="req-rec-1",
                emit_side_effects=False,
            )
        payloads = []
        for rec in cm.records:
            m = rec.getMessage()
            if "identity_obs " in m:
                payloads.append(json.loads(m.split("identity_obs ", 1)[1]))
        completes = [p for p in payloads if p.get("event") == "identity.reconcile.complete"]
        self.assertTrue(completes)
        last = completes[-1]
        self.assertEqual(last.get("new_attachments"), 1)
        self.assertIn(r.assignment_id, last.get("attached_assignment_ids", []))


if __name__ == "__main__":
    unittest.main()
