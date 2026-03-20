"""Tests for identity / assignment historical data reconciliation."""
from __future__ import annotations

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
from backend.services.identity_data_reconciliation import (
    _group_duplicate_contacts_by_email,
    _pick_canonical_contact,
    apply_safe_fixes,
    audit_identity_data,
)


class IdentityDataReconciliationUnitTests(unittest.TestCase):
    def test_group_duplicates_by_email(self):
        rows = [
            {"id": "a", "company_id": "c1", "email_normalized": "X@Y.COM", "linked_auth_user_id": None, "created_at": "2020-01-01"},
            {"id": "b", "company_id": "c1", "email_normalized": "x@y.com", "linked_auth_user_id": None, "created_at": "2021-01-01"},
            {"id": "c", "company_id": "c1", "email_normalized": "", "linked_auth_user_id": None, "created_at": "2021-01-01"},
        ]
        groups = _group_duplicate_contacts_by_email(rows)
        self.assertEqual(len(groups), 1)
        self.assertEqual({g["id"] for g in groups[0]}, {"a", "b"})

    def test_pick_canonical_prefers_linked(self):
        u1, u2 = str(uuid.uuid4()), str(uuid.uuid4())
        group = [
            {"id": "a", "company_id": "c", "email_normalized": "e@e.com", "linked_auth_user_id": None, "created_at": "2022-01-01"},
            {"id": "b", "company_id": "c", "email_normalized": "e@e.com", "linked_auth_user_id": u1, "created_at": "2020-01-01"},
        ]
        canon, reason = _pick_canonical_contact(group)
        self.assertEqual(reason, "")
        self.assertEqual(canon["id"], "b")

    def test_pick_canonical_conflict_two_users(self):
        u1, u2 = str(uuid.uuid4()), str(uuid.uuid4())
        group = [
            {"id": "a", "company_id": "c", "email_normalized": "e@e.com", "linked_auth_user_id": u1, "created_at": "2020-01-01"},
            {"id": "b", "company_id": "c", "email_normalized": "e@e.com", "linked_auth_user_id": u2, "created_at": "2021-01-01"},
        ]
        canon, reason = _pick_canonical_contact(group)
        self.assertIsNone(canon)
        self.assertEqual(reason, "conflicting_linked_auth_user_id")


class IdentityDataReconciliationDbTests(unittest.TestCase):
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

    def test_merge_duplicate_contacts_apply_and_dry_run(self):
        db = self.db
        cid = "co-dup-1"
        now = datetime.utcnow().isoformat()
        with db.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO companies (id, name, created_at) VALUES (:id, :n, :ca)"),
                {"id": cid, "n": "Dup Co", "ca": now},
            )
        try:
            with db.engine.begin() as conn:
                conn.execute(text("DROP INDEX IF EXISTS idx_employee_contacts_company_email_unique"))
        except Exception:
            pass
        ec1, ec2 = str(uuid.uuid4()), str(uuid.uuid4())
        email = "dup.person@example.com"
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO employee_contacts (id, company_id, invite_key, email_normalized, "
                    "first_name, last_name, linked_auth_user_id, created_at, updated_at) "
                    "VALUES (:id, :c, :ik, :en, NULL, NULL, NULL, :ca, :ua)"
                ),
                {"id": ec1, "c": cid, "ik": email, "en": email, "ca": now, "ua": now},
            )
            conn.execute(
                text(
                    "INSERT INTO employee_contacts (id, company_id, invite_key, email_normalized, "
                    "first_name, last_name, linked_auth_user_id, created_at, updated_at) "
                    "VALUES (:id, :c, :ik, :en, NULL, NULL, NULL, :ca, :ua)"
                ),
                {"id": ec2, "c": cid, "ik": "legacy-key", "en": email, "ca": now, "ua": now},
            )

        report = audit_identity_data(db.engine)
        self.assertGreaterEqual(report.counts.get("duplicate_contact_groups", 0), 1)
        self.assertTrue(any(f.get("action") == "merge_duplicate_employee_contacts" for f in report.auto_fixes))

        apply_safe_fixes(db.engine, report, dry_run=True)
        with db.engine.connect() as conn:
            n = conn.execute(text("SELECT COUNT(*) AS n FROM employee_contacts")).scalar()
        self.assertEqual(int(n), 2)

        apply_safe_fixes(db.engine, report, dry_run=False)
        with db.engine.connect() as conn:
            n = conn.execute(text("SELECT COUNT(*) AS n FROM employee_contacts")).scalar()
        self.assertEqual(int(n), 1)

    def test_audit_empty_db_no_errors(self):
        db = self.db
        report = audit_identity_data(db.engine)
        self.assertIsInstance(report.counts, dict)
        self.assertGreaterEqual(report.counts.get("assignment_missing_employee_contact_id", 0), 0)
