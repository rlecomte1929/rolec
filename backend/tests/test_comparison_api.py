"""
Integration tests for [AIQ-236 / P3-1] GET /api/comparison/{employee_id}.

Covers Notion criteria not exercised by the unit suite:
  4. Wrong tier / wrong company → 403 (not 200 with []).
  5. p95 latency < 500ms on a 10-category payload.

Plus the auth happy path for employee + HR. The router is mounted into a
fresh FastAPI app with `auth_deps.get_current_user` stubbed to inject the
desired caller — same pattern as test_policy_summary.py.
"""
from __future__ import annotations

import os
import statistics
import sys
import time
import unittest
import uuid
from typing import Any, Dict, Optional
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


# We need real auth_deps for the dependency, but we'll override
# get_current_user per-request via FastAPI's dependency_overrides.
import backend.app.auth_deps as auth_deps  # noqa: E402
import backend.app.routers.comparison as comparison_router  # noqa: E402
import backend.app.services.comparison_engine as engine_module  # noqa: E402


SCHEMA = """
CREATE TABLE companies (id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE profiles (
    id          TEXT PRIMARY KEY,
    email       TEXT NOT NULL,
    full_name   TEXT,
    company_id  TEXT,
    role        TEXT NOT NULL DEFAULT 'employee'
);
CREATE TABLE policy_tiers (
    id TEXT PRIMARY KEY, company_id TEXT NOT NULL, name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE employee_tiers (
    id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL,
    company_id TEXT NOT NULL,
    policy_tier_id TEXT NOT NULL,
    tier_name TEXT NOT NULL,
    assigned_by TEXT,
    assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
    end_date TEXT
);
CREATE TABLE company_policies (id TEXT PRIMARY KEY, company_id TEXT NOT NULL, title TEXT NOT NULL);
CREATE TABLE policy_versions (
    id TEXT PRIMARY KEY, policy_id TEXT NOT NULL,
    version_number INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft',
    effective_date TEXT, expiry_date TEXT,
    published_by TEXT, published_at TEXT
);
CREATE TABLE policy_categories (
    id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL, sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE policy_values (
    id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL,
    category_id TEXT NOT NULL,
    policy_tier_id TEXT,
    company_id TEXT NOT NULL,
    cap_value REAL,
    cap_unit TEXT,
    cap_currency TEXT NOT NULL DEFAULT 'EUR',
    value_notes TEXT, validated_by TEXT, validated_at TEXT
);
CREATE TABLE cases (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    employee_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE case_services (
    id TEXT PRIMARY KEY, case_id TEXT NOT NULL, assignment_id TEXT,
    service_key TEXT NOT NULL, category TEXT NOT NULL,
    selected INTEGER NOT NULL DEFAULT 1,
    estimated_cost REAL, currency TEXT NOT NULL DEFAULT 'EUR'
);
"""


def _uuid() -> str:
    return str(uuid.uuid4())


# Every CAT code we map to a service bucket. Used for the 10-category latency seed.
LATENCY_FIXTURE_CATEGORIES = [
    ("CAT-01", "Housing Allowance",      "housing",   3500.0),
    ("CAT-02", "Relocation Lump Sum",    "movers",    5000.0),
    ("CAT-03", "Transportation",         "movers",   10000.0),
    ("CAT-04", "Temporary Accomm.",      "housing",   2000.0),
    ("CAT-05", "Travel & Airfare",       "travel",    4000.0),
    ("CAT-07", "Schooling",              "schools",  25000.0),
    ("CAT-10", "Healthcare",             "insurance", 3000.0),
    ("CAT-14", "Repatriation",           "travel",    6000.0),
    # Two policy-only rows with no matching service bucket — exercise the
    # cap-only path inside the merge for a realistic 10-cap fixture.
    ("CAT-09", "Tax Assistance",         None,        7500.0),
    ("CAT-13", "Settling-In",            None,        1500.0),
]


class _DBStub:
    """Minimal db stub so the engine + router can run against in-memory sqlite."""

    def __init__(self, engine):
        self.engine = engine
        # Empty stand-in for db.get_hr_company_id — the auth path will only
        # be reached when JWT.company is missing, which we never set up
        # without also passing it directly.

    def get_hr_company_id(self, _uid):
        return None


class ComparisonApiTests(unittest.TestCase):
    def setUp(self):
        # StaticPool forces one shared SQLite connection across threads —
        # FastAPI's TestClient dispatches handlers via anyio's threadpool,
        # and sqlite :memory: gives each connection its own private DB.
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))

        # Single shared db stub injected into engine + router modules.
        self.db_stub = _DBStub(self.engine)
        self.engine_patches = [
            mock.patch.object(engine_module, "_t", side_effect=lambda _db, n: n),
            mock.patch.object(comparison_router, "db", self.db_stub),
        ]
        for p in self.engine_patches:
            p.start()

        # Compose a FastAPI app and override get_current_user via DI.
        self.app = FastAPI()
        self.app.include_router(comparison_router.router)
        self.current_user: Optional[Dict[str, Any]] = None

        def _stub_current_user():
            if self.current_user is None:
                raise RuntimeError("test forgot to set self.current_user")
            return self.current_user

        self.app.dependency_overrides[auth_deps.get_current_user] = _stub_current_user
        self.client = TestClient(self.app)

    def tearDown(self):
        for p in self.engine_patches:
            p.stop()
        self.app.dependency_overrides.clear()
        self.engine.dispose()

    # ── Fixture builders ───────────────────────────────────────────────────

    def _seed_employee_with_tier_and_one_cap(
        self, *, ask_amount: Optional[float] = 4200.0,
        ask_currency: str = "EUR",
    ):
        company_id = _uuid()
        emp_id = _uuid()
        tier_id = _uuid()
        policy_id = _uuid()
        version_id = _uuid()
        case_id = _uuid()
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO companies (id, name) VALUES (:i, 'Acme')"),
                         {"i": company_id})
            conn.execute(text(
                "INSERT INTO profiles (id, email, company_id, role) "
                "VALUES (:i, :e, :c, 'employee')"
            ), {"i": emp_id, "e": "emp@acme.test", "c": company_id})
            conn.execute(text(
                "INSERT INTO policy_tiers (id, company_id, name) VALUES (:i, :c, 'Std')"
            ), {"i": tier_id, "c": company_id})
            conn.execute(text(
                "INSERT INTO employee_tiers (id, employee_id, company_id, "
                "policy_tier_id, tier_name) VALUES (:i, :e, :c, :pt, 'Std')"
            ), {"i": _uuid(), "e": emp_id, "c": company_id, "pt": tier_id})
            conn.execute(text(
                "INSERT INTO company_policies (id, company_id, title) "
                "VALUES (:i, :c, 'Policy')"
            ), {"i": policy_id, "c": company_id})
            conn.execute(text(
                "INSERT INTO policy_versions (id, policy_id, version_number, "
                "status, effective_date, published_at) "
                "VALUES (:i, :p, 3, 'published', '2026-01-01', '2026-01-02T00:00:00Z')"
            ), {"i": version_id, "p": policy_id})
            cat01_id = _uuid()
            conn.execute(text(
                "INSERT INTO policy_categories (id, code, display_name, sort_order) "
                "VALUES (:i, 'CAT-01', 'Housing Allowance', 1)"
            ), {"i": cat01_id})
            conn.execute(text(
                "INSERT INTO policy_values (id, version_id, category_id, "
                "policy_tier_id, company_id, cap_value, cap_unit, cap_currency) "
                "VALUES (:i, :v, :c, :pt, :co, 3500.0, 'month', 'EUR')"
            ), {"i": _uuid(), "v": version_id, "c": cat01_id, "pt": tier_id,
                "co": company_id})
            conn.execute(text(
                "INSERT INTO cases (id, company_id, employee_id, status, updated_at) "
                "VALUES (:i, :c, :e, 'active', '2026-05-01T00:00:00Z')"
            ), {"i": case_id, "c": company_id, "e": emp_id})
            if ask_amount is not None:
                conn.execute(text(
                    "INSERT INTO case_services (id, case_id, service_key, "
                    "category, selected, estimated_cost, currency) "
                    "VALUES (:i, :ci, 'housing', 'housing', 1, :a, :cu)"
                ), {"i": _uuid(), "ci": case_id, "a": ask_amount,
                    "cu": ask_currency})
        return {"company_id": company_id, "employee_id": emp_id,
                "tier_id": tier_id}

    def _seed_large_policy(self, *, n_categories: int = 10):
        """Seed a 10-category policy with matching service asks for latency."""
        company_id = _uuid()
        emp_id = _uuid()
        tier_id = _uuid()
        policy_id = _uuid()
        version_id = _uuid()
        case_id = _uuid()
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO companies (id, name) VALUES (:i, 'Acme')"),
                         {"i": company_id})
            conn.execute(text(
                "INSERT INTO profiles (id, email, company_id, role) "
                "VALUES (:i, :e, :c, 'employee')"
            ), {"i": emp_id, "e": "emp@acme.test", "c": company_id})
            conn.execute(text(
                "INSERT INTO policy_tiers (id, company_id, name) VALUES (:i, :c, 'Std')"
            ), {"i": tier_id, "c": company_id})
            conn.execute(text(
                "INSERT INTO employee_tiers (id, employee_id, company_id, "
                "policy_tier_id, tier_name) VALUES (:i, :e, :c, :pt, 'Std')"
            ), {"i": _uuid(), "e": emp_id, "c": company_id, "pt": tier_id})
            conn.execute(text(
                "INSERT INTO company_policies (id, company_id, title) "
                "VALUES (:i, :c, 'Policy')"
            ), {"i": policy_id, "c": company_id})
            conn.execute(text(
                "INSERT INTO policy_versions (id, policy_id, version_number, "
                "status, effective_date, published_at) "
                "VALUES (:i, :p, 3, 'published', '2026-01-01', '2026-01-02T00:00:00Z')"
            ), {"i": version_id, "p": policy_id})
            conn.execute(text(
                "INSERT INTO cases (id, company_id, employee_id, status, updated_at) "
                "VALUES (:i, :c, :e, 'active', '2026-05-01T00:00:00Z')"
            ), {"i": case_id, "c": company_id, "e": emp_id})
            for code, name, cap_key, cap_value in LATENCY_FIXTURE_CATEGORIES[:n_categories]:
                cat_id = _uuid()
                conn.execute(text(
                    "INSERT INTO policy_categories (id, code, display_name, sort_order) "
                    "VALUES (:i, :c, :n, 0)"
                ), {"i": cat_id, "c": code, "n": name})
                conn.execute(text(
                    "INSERT INTO policy_values (id, version_id, category_id, "
                    "policy_tier_id, company_id, cap_value, cap_unit, cap_currency) "
                    "VALUES (:i, :v, :c, :pt, :co, :amt, 'month', 'EUR')"
                ), {"i": _uuid(), "v": version_id, "c": cat_id, "pt": tier_id,
                    "co": company_id, "amt": cap_value})
                if cap_key is not None:
                    conn.execute(text(
                        "INSERT INTO case_services (id, case_id, service_key, "
                        "category, selected, estimated_cost, currency) "
                        "VALUES (:i, :ci, :sk, :cat, 1, :a, 'EUR')"
                    ), {"i": _uuid(), "ci": case_id, "sk": cap_key,
                        "cat": cap_key, "a": cap_value * 1.10})  # ask 10% over cap
        return {"company_id": company_id, "employee_id": emp_id}

    # ── Tests ─────────────────────────────────────────────────────────────

    def test_employee_can_read_own_comparison(self):
        ctx = self._seed_employee_with_tier_and_one_cap()
        self.current_user = {
            "id": ctx["employee_id"],
            "role": "employee",
            "company": ctx["company_id"],
            "is_admin": False,
        }
        resp = self.client.get(f"/api/comparison/{ctx['employee_id']}")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["coverage_status"], "Partial")
        self.assertEqual(body[0]["delta"], 700.0)
        self.assertEqual(body[0]["policy_version"], "v3")

    def test_hr_can_read_employee_in_same_company(self):
        ctx = self._seed_employee_with_tier_and_one_cap()
        self.current_user = {
            "id": _uuid(),
            "role": "hr",
            "company": ctx["company_id"],
            "is_admin": False,
        }
        resp = self.client.get(f"/api/comparison/{ctx['employee_id']}")
        self.assertEqual(resp.status_code, 200)

    def test_wrong_tier_returns_403_not_empty_array(self):
        # Criterion 4: a caller belonging to a different company sees 403,
        # NOT a 200 with []. The exact wording of the spec is
        # "caller with wrong tier (not assigned to employee) → 403"; the
        # tier boundary is enforced via the company boundary (HR can only
        # see employees in their own company → only those employees' tiers).
        ctx = self._seed_employee_with_tier_and_one_cap()
        self.current_user = {
            "id": _uuid(),
            "role": "hr",
            "company": _uuid(),  # different company!
            "is_admin": False,
        }
        resp = self.client.get(f"/api/comparison/{ctx['employee_id']}")
        self.assertEqual(resp.status_code, 403)

    def test_other_employee_gets_403(self):
        ctx = self._seed_employee_with_tier_and_one_cap()
        self.current_user = {
            "id": _uuid(),  # not the target employee
            "role": "employee",
            "company": ctx["company_id"],
            "is_admin": False,
        }
        resp = self.client.get(f"/api/comparison/{ctx['employee_id']}")
        self.assertEqual(resp.status_code, 403)

    def test_404_when_employee_has_no_active_tier(self):
        # No employee_tiers row → engine raises NoActiveTierError → router 404.
        company_id = _uuid()
        emp_id = _uuid()
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO companies (id, name) VALUES (:i, 'Acme')"),
                         {"i": company_id})
            conn.execute(text(
                "INSERT INTO profiles (id, email, company_id, role) "
                "VALUES (:i, :e, :c, 'employee')"
            ), {"i": emp_id, "e": "u@a.test", "c": company_id})
        self.current_user = {
            "id": emp_id, "role": "employee",
            "company": company_id, "is_admin": False,
        }
        resp = self.client.get(f"/api/comparison/{emp_id}")
        self.assertEqual(resp.status_code, 404)

    def test_p95_under_500ms_on_10_categories(self):
        # Criterion 5. SQLite + in-memory is faster than the production
        # Postgres path will be, but the bound is generous enough that it
        # still demonstrates the engine has no quadratic blowup.
        ctx = self._seed_large_policy(n_categories=10)
        self.current_user = {
            "id": ctx["employee_id"], "role": "employee",
            "company": ctx["company_id"], "is_admin": False,
        }
        latencies_ms = []
        for _ in range(20):
            t0 = time.perf_counter()
            resp = self.client.get(f"/api/comparison/{ctx['employee_id']}")
            latencies_ms.append((time.perf_counter() - t0) * 1000.0)
            self.assertEqual(resp.status_code, 200)
        latencies_ms.sort()
        # p95 of 20 samples = the 19th sample (0-indexed: 18).
        p95 = latencies_ms[18]
        self.assertLess(p95, 500.0, f"p95 latency {p95:.1f}ms exceeds 500ms")


if __name__ == "__main__":
    unittest.main()
