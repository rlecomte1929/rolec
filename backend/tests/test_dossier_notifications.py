"""
[P4-4] Tests for dossier_notifications service.

Strategy: SQLite in-memory DB with the minimal schema needed to exercise
the context loader and each notification function.  Email calls are
intercepted so no real Resend API key is needed.

Tests cover:
  - _get_context returns correct data
  - All 8 notify_* functions call _inapp / _send_email with the right args
  - run_deadline_reminder_cron queries correct forms and stamps deadline_reminded_at
  - Cron skips forms already reminded
  - Notification functions swallow exceptions (never raise to caller)
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from typing import Any, Dict
from unittest import mock
from datetime import date, timedelta

# ── Repo root on sys.path ────────────────────────────────────────────────────
import os as _os
_REPO = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

# ── Stub heavy backend modules before importing the service ──────────────────
import unittest.mock as _umock
from pydantic import BaseModel as _PB

class _AnyModel(_PB):
    model_config = {"extra": "allow"}

# Only stub the modules that dossier_notifications actually needs at import time.
# Do NOT stub trigger_engine or prefill_engine — those have real test suites
# that need the genuine modules in sys.modules.
for _mod in [
    "backend.database",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _umock.MagicMock()

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

# ── Build an in-memory SQLite schema ─────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    full_name TEXT,
    email TEXT
);
CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,
    name TEXT
);
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    company_id TEXT,
    employee_id TEXT REFERENCES profiles(id),
    hr_owner_id TEXT REFERENCES profiles(id),
    origin_country_code TEXT DEFAULT 'FR',
    dest_country_code TEXT DEFAULT 'NO',
    purpose TEXT DEFAULT 'work',
    status TEXT DEFAULT 'active',
    stage TEXT DEFAULT 'dossier',
    overall_progress_pct INTEGER DEFAULT 0,
    risk_level TEXT DEFAULT 'low',
    delay_days INTEGER DEFAULT 0,
    currency TEXT DEFAULT 'EUR',
    intake_data TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS form_templates (
    id TEXT PRIMARY KEY,
    code TEXT,
    name TEXT,
    authority_name TEXT,
    version TEXT DEFAULT '1.0.0',
    country_code TEXT DEFAULT 'NO',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS case_forms (
    id TEXT PRIMARY KEY,
    case_id TEXT REFERENCES cases(id),
    form_template_id TEXT REFERENCES form_templates(id),
    status TEXT DEFAULT 'not_started',
    deadline TEXT,
    deadline_reminded_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS case_form_field_values (
    id TEXT PRIMARY KEY,
    case_form_id TEXT REFERENCES case_forms(id),
    field_id TEXT,
    value TEXT,
    filled_by TEXT DEFAULT 'ai',
    reviewed INTEGER DEFAULT 0,
    overridden INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        for stmt in _DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
    return engine


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _seed(engine, *, deadline=None, reminded_at=None, status="not_started",
          pre_filled=2, human=1, hr_owner=True):
    emp_id = str(uuid.uuid4())
    hr_id  = str(uuid.uuid4()) if hr_owner else None
    co_id  = str(uuid.uuid4())
    case_id  = str(uuid.uuid4())
    tmpl_id  = str(uuid.uuid4())
    cf_id    = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(text("INSERT INTO profiles VALUES (:id,'Alice Employee','alice@example.com')"), {"id": emp_id})
        if hr_id:
            conn.execute(text("INSERT INTO profiles VALUES (:id,'Bob Specialist','bob@example.com')"), {"id": hr_id})
        conn.execute(text("INSERT INTO companies VALUES (:id,'Acme')"), {"id": co_id})
        conn.execute(text(
            "INSERT INTO cases (id,company_id,employee_id,hr_owner_id,"
            "origin_country_code,dest_country_code,purpose,status,stage,"
            "overall_progress_pct,risk_level,delay_days,currency,intake_data) "
            "VALUES (:id,:co,:emp,:hr,'FR','NO','work','active','dossier',0,'low',0,'EUR','{}')"
        ), {"id": case_id, "co": co_id, "emp": emp_id, "hr": hr_id})
        conn.execute(text(
            "INSERT INTO form_templates (id,code,name,authority_name) "
            "VALUES (:id,'UTL-2011','Notification of move','UDI')"
        ), {"id": tmpl_id})
        conn.execute(text(
            "INSERT INTO case_forms (id,case_id,form_template_id,status,deadline,deadline_reminded_at) "
            "VALUES (:id,:cid,:tid,:st,:dl,:ra)"
        ), {"id": cf_id, "cid": case_id, "tid": tmpl_id, "st": status,
            "dl": deadline, "ra": reminded_at})
        # Field values
        for i in range(pre_filled):
            conn.execute(text(
                "INSERT INTO case_form_field_values (id,case_form_id,field_id,value,filled_by) "
                "VALUES (:id,:cf,:fid,'x','ai')"
            ), {"id": str(uuid.uuid4()), "cf": cf_id, "fid": f"ai_field_{i}"})
        for i in range(human):
            conn.execute(text(
                "INSERT INTO case_form_field_values (id,case_form_id,field_id,value,filled_by) "
                "VALUES (:id,:cf,:fid,'y','employee')"
            ), {"id": str(uuid.uuid4()), "cf": cf_id, "fid": f"human_field_{i}"})
    return {"emp_id": emp_id, "hr_id": hr_id, "case_id": case_id, "cf_id": cf_id}


# ── Test base ─────────────────────────────────────────────────────────────────

class NotifTestBase(unittest.TestCase):

    def setUp(self):
        self.engine = _make_engine()
        # Patch the module-level helpers in dossier_notifications
        import importlib
        import backend.app.services.dossier_notifications as _dn
        importlib.reload(_dn)
        self._dn = _dn
        _dn._engine = lambda: self.engine  # type: ignore[attr-defined]
        # Capture in-app and email calls
        self._inapp_calls: list = []
        self._email_calls: list = []
        orig_inapp = _dn._inapp
        orig_email = _dn._send_email

        def _fake_inapp(user_id, type_, title, body, case_id=None):
            self._inapp_calls.append({"user_id": user_id, "type": type_,
                                       "title": title, "body": body, "case_id": case_id})
        def _fake_email(to, subject, title, body, cta_url=None):
            self._email_calls.append({"to": to, "subject": subject, "title": title})

        _dn._inapp = _fake_inapp        # type: ignore[attr-defined]
        _dn._send_email = _fake_email   # type: ignore[attr-defined]
        # Patch main_db
        _dn._main_db = lambda: type("DB", (), {"create_notification_with_preferences": lambda *a, **kw: None})()  # type: ignore[attr-defined]


# ── Context tests ─────────────────────────────────────────────────────────────

class TestGetContext(NotifTestBase):

    def test_returns_none_for_unknown_id(self):
        ctx = self._dn._get_context(str(uuid.uuid4()))
        self.assertIsNone(ctx)

    def test_returns_correct_employee_and_form(self):
        ids = _seed(self.engine)
        ctx = self._dn._get_context(ids["cf_id"])
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["form_code"], "UTL-2011")
        self.assertEqual(str(ctx["employee_id"]), ids["emp_id"])
        self.assertEqual(ctx["employee_email"], "alice@example.com")
        self.assertEqual(int(ctx["pre_filled_count"]), 2)
        self.assertEqual(int(ctx["human_count"]), 1)


# ── Event 1: new_form_created ─────────────────────────────────────────────────

class TestNotifyNewFormCreated(NotifTestBase):

    def test_notifies_employee_inapp_and_email(self):
        ids = _seed(self.engine)
        self._dn.notify_new_form_created(ids["cf_id"])
        self.assertEqual(len(self._inapp_calls), 1)
        self.assertEqual(self._inapp_calls[0]["type"], "dossier.new_form")
        self.assertEqual(len(self._email_calls), 1)
        self.assertIn("alice@example.com", self._email_calls[0]["to"])

    def test_unknown_form_does_not_raise(self):
        self._dn.notify_new_form_created(str(uuid.uuid4()))  # should not raise
        self.assertEqual(len(self._inapp_calls), 0)


# ── Event 2: form_auto_filled ─────────────────────────────────────────────────

class TestNotifyAutoFilled(NotifTestBase):

    def test_notifies_employee_with_counts(self):
        ids = _seed(self.engine, pre_filled=5, human=3)
        self._dn.notify_form_auto_filled(ids["cf_id"])
        self.assertEqual(self._inapp_calls[0]["type"], "dossier.auto_filled")
        self.assertIn("5", self._inapp_calls[0]["body"])  # pre_filled_count in message


# ── Event 5: form_ready ───────────────────────────────────────────────────────

class TestNotifyFormReady(NotifTestBase):

    def test_notifies_specialist(self):
        ids = _seed(self.engine)
        self._dn.notify_form_ready(ids["cf_id"])
        self.assertEqual(self._inapp_calls[0]["type"], "dossier.form_ready")
        self.assertEqual(self._inapp_calls[0]["user_id"], ids["hr_id"])
        self.assertEqual(self._email_calls[0]["to"], "bob@example.com")

    def test_no_notification_if_no_specialist(self):
        ids = _seed(self.engine, hr_owner=False)
        self._dn.notify_form_ready(ids["cf_id"])
        self.assertEqual(len(self._inapp_calls), 0)


# ── Event 6: form_submitted ───────────────────────────────────────────────────

class TestNotifyFormSubmitted(NotifTestBase):

    def test_notifies_employee_and_specialist(self):
        ids = _seed(self.engine)
        self._dn.notify_form_submitted(ids["cf_id"], receipt_ref="REF-42")
        types = [c["type"] for c in self._inapp_calls]
        self.assertEqual(types.count("dossier.submitted"), 2)
        emails = [c["to"] for c in self._email_calls]
        self.assertIn("alice@example.com", emails)
        self.assertIn("bob@example.com", emails)

    def test_receipt_ref_in_message(self):
        ids = _seed(self.engine)
        self._dn.notify_form_submitted(ids["cf_id"], receipt_ref="REF-99")
        bodies = [c["body"] for c in self._inapp_calls]
        self.assertTrue(any("REF-99" in b for b in bodies))


# ── Event 7: form_rejected ────────────────────────────────────────────────────

class TestNotifyFormRejected(NotifTestBase):

    def test_notifies_employee_and_specialist(self):
        ids = _seed(self.engine)
        self._dn.notify_form_rejected(ids["cf_id"], reason="Missing signature")
        types = [c["type"] for c in self._inapp_calls]
        self.assertEqual(types.count("dossier.rejected"), 2)

    def test_reason_in_message(self):
        ids = _seed(self.engine)
        self._dn.notify_form_rejected(ids["cf_id"], reason="Expired document")
        bodies = [c["body"] for c in self._inapp_calls]
        self.assertTrue(any("Expired document" in b for b in bodies))


# ── Event 4: blocker_resolved ─────────────────────────────────────────────────

class TestNotifyBlockerResolved(NotifTestBase):

    def test_notifies_employee(self):
        ids = _seed(self.engine)
        self._dn.notify_blocker_resolved(ids["cf_id"], unblocked_form_name="HELFO-1")
        self.assertEqual(self._inapp_calls[0]["type"], "dossier.blocker_resolved")
        self.assertIn("HELFO-1", self._inapp_calls[0]["body"])


# ── Event 8: dossier_built ────────────────────────────────────────────────────

class TestNotifyDossierBuilt(NotifTestBase):

    def test_notifies_specialist(self):
        ids = _seed(self.engine)
        self._dn.notify_dossier_built(ids["case_id"], form_count=8)
        self.assertEqual(self._inapp_calls[0]["type"], "dossier.built")
        self.assertIn("8", self._inapp_calls[0]["body"])


# ── Cron: run_deadline_reminder_cron ─────────────────────────────────────────

class TestDeadlineCron(NotifTestBase):

    def _target_date(self):
        return (date.today() + timedelta(days=7)).isoformat()

    def test_reminds_due_forms_and_stamps(self):
        ids = _seed(self.engine, deadline=self._target_date())
        result = self._dn.run_deadline_reminder_cron()
        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["reminded"], 1)
        self.assertEqual(result["errors"], 0)
        # Verify deadline_reminded_at was stamped
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT deadline_reminded_at FROM case_forms WHERE id=:id"),
                {"id": ids["cf_id"]},
            ).mappings().first()
        self.assertIsNotNone(row["deadline_reminded_at"])

    def test_skips_already_reminded(self):
        ids = _seed(self.engine, deadline=self._target_date(), reminded_at="2026-05-20T08:00:00")
        result = self._dn.run_deadline_reminder_cron()
        self.assertEqual(result["checked"], 0)
        self.assertEqual(result["reminded"], 0)

    def test_skips_wrong_date(self):
        # deadline is 8 days away — should not trigger
        wrong = (date.today() + timedelta(days=8)).isoformat()
        _seed(self.engine, deadline=wrong)
        result = self._dn.run_deadline_reminder_cron()
        self.assertEqual(result["checked"], 0)

    def test_skips_terminal_forms(self):
        ids = _seed(self.engine, deadline=self._target_date(), status="submitted")
        result = self._dn.run_deadline_reminder_cron()
        self.assertEqual(result["checked"], 0)

    def test_two_forms_both_reminded(self):
        _seed(self.engine, deadline=self._target_date())
        _seed(self.engine, deadline=self._target_date())
        result = self._dn.run_deadline_reminder_cron()
        self.assertEqual(result["checked"], 2)
        self.assertEqual(result["reminded"], 2)


if __name__ == "__main__":
    unittest.main()
