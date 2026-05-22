"""
Tests for [P1-6] Employee tier assignment API.

Covers:
  GET    /api/employees/{employee_id}              — happy path + 404 + cross-company
  POST   /api/employees/{employee_id}/tier         — assign + reassign archival
  POST   /api/employees/import                     — CSV happy path + row-level
                                                     errors + idempotency + tier
                                                     validation

Pattern (mirrors test_form_original_pdf.py):
  - SQLite in-memory DB with a tiny schema that matches what the router reads
  - db.engine patched at module level
  - auth_deps stub injected before importing the router so no JWT plumbing
  - Multipart uploads simulated via FastAPI's UploadFile constructed from
    SpooledTemporaryFile — keeps the test handler call identical to what
    FastAPI's request parser produces.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import unittest
import uuid
from tempfile import SpooledTemporaryFile
from typing import Any, Dict, Optional
from unittest import mock

from sqlalchemy import create_engine, text
from fastapi import HTTPException, UploadFile

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Stub auth_deps before importing the router so we don't need JWT setup.
import unittest.mock as _umock  # noqa: E402
if "backend.app.auth_deps" not in sys.modules:
    _stub_auth = _umock.MagicMock()
    _stub_auth.get_current_user = _umock.MagicMock(return_value={"id": "u", "role": "hr"})
    sys.modules["backend.app.auth_deps"] = _stub_auth


import backend.app.routers.employee_tiers as et  # noqa: E402
from backend.app.routers.employee_tiers import (  # noqa: E402
    get_employee_with_tier,
    assign_single_tier,
    import_employee_tiers_csv,
    AssignTierPayload,
)


# ─────────────────────────────────────────────────────────────────────────────
# Minimal schema — the columns the router reads/writes
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE companies (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE profiles (
    id          TEXT PRIMARY KEY,
    email       TEXT NOT NULL,
    full_name   TEXT,
    company_id  TEXT,
    role        TEXT NOT NULL DEFAULT 'employee'
);
CREATE TABLE policy_tiers (
    id          TEXT PRIMARY KEY,
    company_id  TEXT NOT NULL,
    name        TEXT NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE employee_tiers (
    id              TEXT PRIMARY KEY,
    employee_id     TEXT NOT NULL,
    company_id      TEXT NOT NULL,
    policy_tier_id  TEXT NOT NULL,
    tier_name       TEXT NOT NULL,
    assigned_by     TEXT,
    assigned_at     TEXT NOT NULL DEFAULT (datetime('now')),
    end_date        TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX employee_tiers_current_unique
    ON employee_tiers (employee_id)
    WHERE end_date IS NULL;
CREATE TABLE audit_log (
    id            TEXT NOT NULL,
    actor_user_id TEXT NOT NULL,
    action_type   TEXT NOT NULL,
    target_type   TEXT NOT NULL,
    target_id     TEXT,
    metadata_json TEXT,
    created_at    TEXT NOT NULL
);
"""


def _uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# Seed helpers
# ─────────────────────────────────────────────────────────────────────────────

def _seed_company(conn, *, cid: str, name: str = "Acme") -> None:
    conn.execute(text("INSERT INTO companies (id, name) VALUES (:id, :n)"),
                 {"id": cid, "n": name})


def _seed_profile(conn, *, pid: str, email: str, company_id: str,
                  full_name: str = "Test User", role: str = "employee") -> None:
    conn.execute(text(
        "INSERT INTO profiles (id, email, full_name, company_id, role) "
        "VALUES (:id, :e, :n, :c, :r)"
    ), {"id": pid, "e": email, "n": full_name, "c": company_id, "r": role})


def _seed_policy_tier(conn, *, tid: str, company_id: str, name: str,
                      active: bool = True) -> None:
    conn.execute(text(
        "INSERT INTO policy_tiers (id, company_id, name, is_active) "
        "VALUES (:id, :c, :n, :a)"
    ), {"id": tid, "c": company_id, "n": name, "a": 1 if active else 0})


def _hr_user(actor_id: str, company_id: str) -> Dict[str, Any]:
    return {"id": actor_id, "role": "hr", "company_id": company_id}


def _admin_user(actor_id: str) -> Dict[str, Any]:
    return {"id": actor_id, "role": "admin", "company_id": None}


def _build_upload_file(content: str, filename: str = "tiers.csv") -> UploadFile:
    """Construct an UploadFile the way FastAPI would, from a string body."""
    spooled = SpooledTemporaryFile()
    spooled.write(content.encode("utf-8"))
    spooled.seek(0)
    return UploadFile(filename=filename, file=spooled)


def _run(coro):
    """Run an async handler synchronously inside the test."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ─────────────────────────────────────────────────────────────────────────────
# Test suite
# ─────────────────────────────────────────────────────────────────────────────

class EmployeeTierTests(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))

        self.engine_patcher = mock.patch.object(et.db, "engine", self.engine)
        self.engine_patcher.start()

    def tearDown(self):
        self.engine_patcher.stop()
        self.engine.dispose()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _seed_basic_company(self, *, with_tiers=("Standard", "Premium")):
        company_id = _uuid()
        hr_id = _uuid()
        with self.engine.begin() as conn:
            _seed_company(conn, cid=company_id)
            _seed_profile(conn, pid=hr_id, email="hr@acme.test",
                          company_id=company_id, role="hr")
            tier_ids = {}
            for name in with_tiers:
                tid = _uuid()
                _seed_policy_tier(conn, tid=tid, company_id=company_id, name=name)
                tier_ids[name] = tid
        return company_id, hr_id, tier_ids

    def _count_active_tier_rows(self, employee_id: str) -> int:
        with self.engine.connect() as conn:
            return conn.execute(text(
                "SELECT count(*) FROM employee_tiers "
                "WHERE employee_id = :e AND end_date IS NULL"
            ), {"e": employee_id}).scalar()

    def _count_total_tier_rows(self, employee_id: str) -> int:
        with self.engine.connect() as conn:
            return conn.execute(text(
                "SELECT count(*) FROM employee_tiers WHERE employee_id = :e"
            ), {"e": employee_id}).scalar()

    def _count_audit_rows(self, employee_id: str) -> int:
        with self.engine.connect() as conn:
            return conn.execute(text(
                "SELECT count(*) FROM audit_log "
                "WHERE action_type = 'employee_tier.assigned' "
                "AND target_id = :id"
            ), {"id": employee_id}).scalar()

    # ── GET /api/employees/{id} ──────────────────────────────────────────────

    def test_get_employee_returns_profile_without_tier_when_unassigned(self):
        company_id, hr_id, _ = self._seed_basic_company()
        emp_id = _uuid()
        with self.engine.begin() as conn:
            _seed_profile(conn, pid=emp_id, email="alice@acme.test",
                          company_id=company_id, full_name="Alice A")

        res = get_employee_with_tier(emp_id, _hr_user(hr_id, company_id))
        self.assertEqual(res.id, emp_id)
        self.assertEqual(res.email, "alice@acme.test")
        self.assertIsNone(res.tier)

    def test_get_employee_returns_current_tier(self):
        company_id, hr_id, tier_ids = self._seed_basic_company()
        emp_id = _uuid()
        with self.engine.begin() as conn:
            _seed_profile(conn, pid=emp_id, email="bob@acme.test",
                          company_id=company_id)

        assign_single_tier(emp_id, AssignTierPayload(tier_name="Premium"),
                           _hr_user(hr_id, company_id))

        res = get_employee_with_tier(emp_id, _hr_user(hr_id, company_id))
        self.assertIsNotNone(res.tier)
        self.assertEqual(res.tier.tier_name, "Premium")
        self.assertEqual(res.tier.policy_tier_id, tier_ids["Premium"])
        self.assertEqual(res.tier.assigned_by, hr_id)

    def test_get_employee_404_when_unknown(self):
        company_id, hr_id, _ = self._seed_basic_company()
        with self.assertRaises(HTTPException) as ctx:
            get_employee_with_tier(_uuid(), _hr_user(hr_id, company_id))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_get_employee_403_when_cross_company(self):
        company_a, hr_id, _ = self._seed_basic_company()
        company_b = _uuid()
        emp_in_b = _uuid()
        with self.engine.begin() as conn:
            _seed_company(conn, cid=company_b, name="OtherCo")
            _seed_profile(conn, pid=emp_in_b, email="x@otherco.test",
                          company_id=company_b)

        with self.assertRaises(HTTPException) as ctx:
            get_employee_with_tier(emp_in_b, _hr_user(hr_id, company_a))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_get_employee_403_when_caller_is_employee_role(self):
        company_id, _, _ = self._seed_basic_company()
        emp_id = _uuid()
        with self.engine.begin() as conn:
            _seed_profile(conn, pid=emp_id, email="self@acme.test",
                          company_id=company_id)

        with self.assertRaises(HTTPException) as ctx:
            get_employee_with_tier(emp_id, {
                "id": emp_id, "role": "employee", "company_id": company_id,
            })
        self.assertEqual(ctx.exception.status_code, 403)

    # ── POST /api/employees/{id}/tier ────────────────────────────────────────

    def test_single_assign_creates_active_row(self):
        company_id, hr_id, tier_ids = self._seed_basic_company()
        emp_id = _uuid()
        with self.engine.begin() as conn:
            _seed_profile(conn, pid=emp_id, email="alice@acme.test",
                          company_id=company_id)

        res = assign_single_tier(
            emp_id,
            AssignTierPayload(tier_name="Standard"),
            _hr_user(hr_id, company_id),
        )
        self.assertEqual(res.tier.tier_name, "Standard")
        self.assertEqual(res.tier.policy_tier_id, tier_ids["Standard"])
        self.assertEqual(self._count_active_tier_rows(emp_id), 1)
        self.assertEqual(self._count_audit_rows(emp_id), 1)

    def test_reassign_archives_previous_and_creates_new(self):
        company_id, hr_id, _ = self._seed_basic_company()
        emp_id = _uuid()
        with self.engine.begin() as conn:
            _seed_profile(conn, pid=emp_id, email="alice@acme.test",
                          company_id=company_id)

        assign_single_tier(emp_id, AssignTierPayload(tier_name="Standard"),
                           _hr_user(hr_id, company_id))
        assign_single_tier(emp_id, AssignTierPayload(tier_name="Premium"),
                           _hr_user(hr_id, company_id))

        self.assertEqual(self._count_active_tier_rows(emp_id), 1)
        self.assertEqual(self._count_total_tier_rows(emp_id), 2)
        # Audit log has 2 rows now (one per assignment)
        self.assertEqual(self._count_audit_rows(emp_id), 2)

        res = get_employee_with_tier(emp_id, _hr_user(hr_id, company_id))
        self.assertEqual(res.tier.tier_name, "Premium")

    def test_single_assign_422_when_tier_unknown(self):
        company_id, hr_id, _ = self._seed_basic_company()
        emp_id = _uuid()
        with self.engine.begin() as conn:
            _seed_profile(conn, pid=emp_id, email="alice@acme.test",
                          company_id=company_id)

        with self.assertRaises(HTTPException) as ctx:
            assign_single_tier(
                emp_id,
                AssignTierPayload(tier_name="Ghost-Tier"),
                _hr_user(hr_id, company_id),
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("Ghost-Tier", str(ctx.exception.detail))

    def test_single_assign_tier_lookup_is_case_insensitive(self):
        company_id, hr_id, _ = self._seed_basic_company()
        emp_id = _uuid()
        with self.engine.begin() as conn:
            _seed_profile(conn, pid=emp_id, email="alice@acme.test",
                          company_id=company_id)

        res = assign_single_tier(
            emp_id,
            AssignTierPayload(tier_name="premium"),  # lowercase
            _hr_user(hr_id, company_id),
        )
        # Stored with canonical casing from policy_tiers.name
        self.assertEqual(res.tier.tier_name, "Premium")

    def test_single_assign_403_when_caller_not_hr_or_admin(self):
        company_id, _, _ = self._seed_basic_company()
        emp_id = _uuid()
        with self.engine.begin() as conn:
            _seed_profile(conn, pid=emp_id, email="alice@acme.test",
                          company_id=company_id)

        with self.assertRaises(HTTPException) as ctx:
            assign_single_tier(
                emp_id,
                AssignTierPayload(tier_name="Standard"),
                {"id": _uuid(), "role": "employee", "company_id": company_id},
            )
        self.assertEqual(ctx.exception.status_code, 403)

    # ── POST /api/employees/import (CSV) ─────────────────────────────────────

    def test_csv_import_happy_path(self):
        company_id, hr_id, _ = self._seed_basic_company()
        ids = [_uuid() for _ in range(3)]
        with self.engine.begin() as conn:
            _seed_profile(conn, pid=ids[0], email="jane@acme.test",
                          company_id=company_id, full_name="Jane Smith")
            _seed_profile(conn, pid=ids[1], email="john@acme.test",
                          company_id=company_id, full_name="John Doe")
            _seed_profile(conn, pid=ids[2], email="kim@acme.test",
                          company_id=company_id, full_name="Kim K")

        csv_body = (
            "name,email,tier_name\n"
            "Jane Smith,jane@acme.test,Standard\n"
            "John Doe,john@acme.test,Premium\n"
            "Kim K,kim@acme.test,Standard\n"
        )
        res = _run(import_employee_tiers_csv(
            _build_upload_file(csv_body),
            _hr_user(hr_id, company_id),
        ))

        self.assertEqual(res.total_rows, 3)
        self.assertEqual(len(res.successes), 3)
        self.assertEqual(len(res.errors), 0)
        for emp_id in ids:
            self.assertEqual(self._count_active_tier_rows(emp_id), 1)

    def test_csv_import_reports_row_level_errors_for_unknown_tier(self):
        company_id, hr_id, _ = self._seed_basic_company()
        emp_ids = [_uuid() for _ in range(2)]
        with self.engine.begin() as conn:
            _seed_profile(conn, pid=emp_ids[0], email="a@acme.test",
                          company_id=company_id)
            _seed_profile(conn, pid=emp_ids[1], email="b@acme.test",
                          company_id=company_id)

        csv_body = (
            "name,email,tier_name\n"
            "A,a@acme.test,Standard\n"
            "B,b@acme.test,Phantom\n"  # unknown tier
        )
        res = _run(import_employee_tiers_csv(
            _build_upload_file(csv_body),
            _hr_user(hr_id, company_id),
        ))

        self.assertEqual(res.total_rows, 2)
        self.assertEqual(len(res.successes), 1)
        self.assertEqual(len(res.errors), 1)
        self.assertEqual(res.errors[0].row, 3)
        self.assertEqual(res.errors[0].email, "b@acme.test")
        self.assertIn("Phantom", res.errors[0].message)

    def test_csv_import_reports_unknown_email(self):
        company_id, hr_id, _ = self._seed_basic_company()
        # Note: no profile seeded for ghost@acme.test
        csv_body = (
            "name,email,tier_name\n"
            "Ghost,ghost@acme.test,Standard\n"
        )
        res = _run(import_employee_tiers_csv(
            _build_upload_file(csv_body),
            _hr_user(hr_id, company_id),
        ))
        self.assertEqual(len(res.successes), 0)
        self.assertEqual(len(res.errors), 1)
        self.assertIn("No profile", res.errors[0].message)

    def test_csv_import_is_idempotent_for_repeated_email(self):
        """Re-importing the same email twice keeps one active row, total = 2."""
        company_id, hr_id, _ = self._seed_basic_company()
        emp_id = _uuid()
        with self.engine.begin() as conn:
            _seed_profile(conn, pid=emp_id, email="alice@acme.test",
                          company_id=company_id)

        csv_body = (
            "name,email,tier_name\n"
            "Alice,alice@acme.test,Standard\n"
        )
        _run(import_employee_tiers_csv(
            _build_upload_file(csv_body), _hr_user(hr_id, company_id),
        ))
        _run(import_employee_tiers_csv(
            _build_upload_file(csv_body), _hr_user(hr_id, company_id),
        ))

        self.assertEqual(self._count_active_tier_rows(emp_id), 1)
        self.assertEqual(self._count_total_tier_rows(emp_id), 2)

    def test_csv_import_tolerates_excel_bom(self):
        company_id, hr_id, _ = self._seed_basic_company()
        emp_id = _uuid()
        with self.engine.begin() as conn:
            _seed_profile(conn, pid=emp_id, email="alice@acme.test",
                          company_id=company_id)

        # UTF-8 BOM prefix as Excel exports
        csv_body = "﻿name,email,tier_name\nAlice,alice@acme.test,Standard\n"
        res = _run(import_employee_tiers_csv(
            _build_upload_file(csv_body),
            _hr_user(hr_id, company_id),
        ))
        self.assertEqual(len(res.successes), 1)
        self.assertEqual(len(res.errors), 0)

    def test_csv_import_422_when_header_missing_required_column(self):
        company_id, hr_id, _ = self._seed_basic_company()
        csv_body = "name,email\nAlice,a@acme.test\n"  # no tier_name
        with self.assertRaises(HTTPException) as ctx:
            _run(import_employee_tiers_csv(
                _build_upload_file(csv_body),
                _hr_user(hr_id, company_id),
            ))
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("tier_name", str(ctx.exception.detail))

    def test_csv_import_422_on_empty_file(self):
        company_id, hr_id, _ = self._seed_basic_company()
        with self.assertRaises(HTTPException) as ctx:
            _run(import_employee_tiers_csv(
                _build_upload_file(""),
                _hr_user(hr_id, company_id),
            ))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_csv_import_reports_blank_email(self):
        company_id, hr_id, _ = self._seed_basic_company()
        csv_body = (
            "name,email,tier_name\n"
            ",,Standard\n"
        )
        res = _run(import_employee_tiers_csv(
            _build_upload_file(csv_body),
            _hr_user(hr_id, company_id),
        ))
        self.assertEqual(len(res.errors), 1)
        self.assertEqual(res.errors[0].row, 2)
        self.assertIn("email", res.errors[0].message)

    def test_csv_import_403_when_caller_is_employee(self):
        company_id, _, _ = self._seed_basic_company()
        csv_body = "name,email,tier_name\nA,a@acme.test,Standard\n"
        with self.assertRaises(HTTPException) as ctx:
            _run(import_employee_tiers_csv(
                _build_upload_file(csv_body),
                {"id": _uuid(), "role": "employee", "company_id": company_id},
            ))
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
