"""[VND-05] create_rfq must use the real public.vendors columns.

Regression lock for the prod 500: the vendor lookup used contact_email / corridors / is_approved,
none of which exist on public.vendors (real: email, countries_served, is_active). SQLite-backed,
prod-shaped schema; calls the handler directly. Does NOT set DATABASE_URL at import.
"""
from __future__ import annotations

import asyncio
import re
import unittest
from unittest import mock

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import create_engine, event, text

import backend.app.routers.hr_rfq as hr_rfq
from backend.app.routers.hr_rfq import RfqCreateRequest

# Strip Postgres-only CAST(:x AS jsonb) so the immigration_context insert runs on SQLite.
_PG_CAST_RE = re.compile(r"CAST\((:?\w+|\?) AS jsonb\)", re.IGNORECASE)

SCHEMA = """
CREATE TABLE vendors_legacy (
  id TEXT PRIMARY KEY, name TEXT, email TEXT, countries_served TEXT, is_active INTEGER
);
CREATE TABLE rfq_requests (
  id TEXT PRIMARY KEY, case_id TEXT, vendor_id TEXT, org_id TEXT, service_category TEXT,
  move_date TEXT, budget_range TEXT, special_requirements TEXT, immigration_context TEXT,
  hr_user_id TEXT, hr_email TEXT, hr_name TEXT, status TEXT, created_at TEXT, updated_at TEXT
);
"""

HR = {"id": "hr-1", "role": "HR", "company": "co-1", "email": "hr@example.com"}


class CreateRfqTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

        @event.listens_for(self.engine, "before_cursor_execute", retval=True)
        def _strip_jsonb_cast(conn, cursor, statement, parameters, context, executemany):
            return _PG_CAST_RE.sub(r"\1", statement), parameters

        with self.engine.begin() as c:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    c.execute(text(stmt))
            c.execute(text(
                "INSERT INTO vendors_legacy (id, name, email, countries_served, is_active) "
                "VALUES ('v1', 'SIRVA', 'vendor@example.com', 'DE', 1)"
            ))

        self._patch(hr_rfq.db, "engine", self.engine)
        self._patch(hr_rfq.db, "get_hr_company_id", lambda *_a, **_k: None)
        self._patch(hr_rfq.db, "get_profile_record", lambda *_a, **_k: None)
        # Audit + email are out of scope here (audit table / SMTP); make them no-ops.
        self._patch(hr_rfq, "insert_audit_log", lambda *_a, **_k: None)

    def _patch(self, target, attr, value):
        p = mock.patch.object(target, attr, value)
        p.start()
        self.addCleanup(p.stop)

    def _rows(self):
        with self.engine.connect() as c:
            return list(c.execute(text("SELECT * FROM rfq_requests")).mappings())

    def test_create_rfq_inserts_row(self):
        body = RfqCreateRequest(case_id="case-1", vendor_id="v1", service_category="moving")
        res = asyncio.run(hr_rfq.create_rfq(body=body, background_tasks=BackgroundTasks(), user=HR))
        self.assertTrue(res.get("ok"))
        self.assertEqual(res.get("vendor_name"), "SIRVA")
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["vendor_id"], "v1")
        self.assertEqual(rows[0]["org_id"], "co-1")  # org_id = resolved HR company
        self.assertEqual(rows[0]["status"], "sent")

    def test_missing_vendor_404(self):
        body = RfqCreateRequest(case_id="case-1", vendor_id="does-not-exist", service_category="moving")
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(hr_rfq.create_rfq(body=body, background_tasks=BackgroundTasks(), user=HR))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_inactive_vendor_404(self):
        with self.engine.begin() as c:
            c.execute(text("UPDATE vendors_legacy SET is_active = 0 WHERE id = 'v1'"))
        body = RfqCreateRequest(case_id="case-1", vendor_id="v1", service_category="moving")
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(hr_rfq.create_rfq(body=body, background_tasks=BackgroundTasks(), user=HR))
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
