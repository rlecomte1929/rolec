"""
Tests for [AIQ-236 / P3-1] backend.app.services.comparison_engine.

Covers the Notion validation criteria 1, 2, 3 (delta math), the active-tier
SQL filter, the no-policy 404/409 error paths, and the currency_warning flag.
Criterion 4 (403 on wrong tier) is exercised in test_comparison_api.py
because it lives in the router. Criterion 5 (p95 < 500ms) is asserted in
the integration test.

Pattern mirrors test_policy_summary.py / test_employee_tiers.py:
in-memory SQLite, minimal schema, db.engine patched at module level.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from typing import Any, Optional
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Stub auth_deps before importing the engine — it imports backend.app.schemas
# transitively via the router's neighbours, and we want zero JWT plumbing.
import unittest.mock as _umock  # noqa: E402
if "backend.app.auth_deps" not in sys.modules:
    _stub = _umock.MagicMock()
    _stub.get_current_user = _umock.MagicMock(return_value={"id": "u", "role": "hr"})
    sys.modules["backend.app.auth_deps"] = _stub


import backend.app.services.comparison_engine as engine  # noqa: E402
from backend.app.services.comparison_engine import (  # noqa: E402
    NoActiveTierError,
    NoPublishedPolicyError,
    compute_comparison,
    merge_caps_and_asks,
)


# ─────────────────────────────────────────────────────────────────────────────
# Minimal schema — every column the engine touches.
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
    id         TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    name       TEXT NOT NULL,
    is_active  INTEGER NOT NULL DEFAULT 1
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
CREATE TABLE company_policies (
    id         TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    title      TEXT NOT NULL
);
CREATE TABLE policy_versions (
    id             TEXT PRIMARY KEY,
    policy_id      TEXT NOT NULL,
    version_number INTEGER NOT NULL DEFAULT 1,
    status         TEXT NOT NULL DEFAULT 'draft',
    effective_date TEXT,
    expiry_date    TEXT,
    published_by   TEXT,
    published_at   TEXT
);
CREATE TABLE policy_categories (
    id           TEXT PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    sort_order   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE policy_values (
    id              TEXT PRIMARY KEY,
    version_id      TEXT NOT NULL,
    category_id     TEXT NOT NULL,
    policy_tier_id  TEXT,
    company_id      TEXT NOT NULL,
    cap_value       REAL,
    cap_unit        TEXT,
    cap_currency    TEXT NOT NULL DEFAULT 'EUR',
    value_notes     TEXT,
    validated_by    TEXT,
    validated_at    TEXT
);
CREATE TABLE cases (
    id          TEXT PRIMARY KEY,
    company_id  TEXT NOT NULL,
    employee_id TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE case_services (
    id              TEXT PRIMARY KEY,
    case_id         TEXT NOT NULL,
    assignment_id   TEXT,
    service_key     TEXT NOT NULL,
    category        TEXT NOT NULL,
    selected        INTEGER NOT NULL DEFAULT 1,
    estimated_cost  REAL,
    currency        TEXT NOT NULL DEFAULT 'EUR'
);
"""


def _uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# Seed helpers
# ─────────────────────────────────────────────────────────────────────────────

def _seed_company(conn, cid: str) -> None:
    conn.execute(text("INSERT INTO companies (id, name) VALUES (:id, 'Acme')"),
                 {"id": cid})


def _seed_employee(conn, *, eid: str, company_id: str) -> None:
    conn.execute(text(
        "INSERT INTO profiles (id, email, company_id, role) "
        "VALUES (:id, :e, :c, 'employee')"
    ), {"id": eid, "e": f"{eid}@acme.test", "c": company_id})


def _seed_tier(conn, *, tid: str, company_id: str, name: str = "Standard") -> None:
    conn.execute(text(
        "INSERT INTO policy_tiers (id, company_id, name) VALUES (:id, :c, :n)"
    ), {"id": tid, "c": company_id, "n": name})


def _seed_employee_tier(conn, *, employee_id: str, company_id: str,
                        policy_tier_id: str, tier_name: str,
                        end_date: Optional[str] = None) -> None:
    conn.execute(text(
        "INSERT INTO employee_tiers (id, employee_id, company_id, policy_tier_id, "
        "tier_name, end_date) VALUES (:id, :e, :c, :pt, :n, :ed)"
    ), {"id": _uuid(), "e": employee_id, "c": company_id,
        "pt": policy_tier_id, "n": tier_name, "ed": end_date})


def _seed_company_policy(conn, *, pid: str, company_id: str) -> None:
    conn.execute(text(
        "INSERT INTO company_policies (id, company_id, title) "
        "VALUES (:id, :cid, 'Policy')"
    ), {"id": pid, "cid": company_id})


def _seed_version(conn, *, vid: str, policy_id: str, version_number: int = 3,
                  status: str = "published",
                  effective_date: str = "2026-01-01",
                  published_at: str = "2026-01-02T00:00:00Z") -> None:
    conn.execute(text(
        "INSERT INTO policy_versions (id, policy_id, version_number, status, "
        "effective_date, published_at) "
        "VALUES (:id, :pid, :vn, :s, :ed, :pat)"
    ), {"id": vid, "pid": policy_id, "vn": version_number, "s": status,
        "ed": effective_date, "pat": published_at})


def _seed_category(conn, *, code: str, name: str, sort_order: int = 1) -> str:
    cid = _uuid()
    conn.execute(text(
        "INSERT INTO policy_categories (id, code, display_name, sort_order) "
        "VALUES (:id, :c, :n, :s)"
    ), {"id": cid, "c": code, "n": name, "s": sort_order})
    return cid


def _seed_value(conn, *, version_id: str, category_id: str, company_id: str,
                policy_tier_id: Optional[str], cap_value: float,
                cap_unit: str = "month", cap_currency: str = "EUR") -> None:
    conn.execute(text(
        "INSERT INTO policy_values (id, version_id, category_id, policy_tier_id, "
        "company_id, cap_value, cap_unit, cap_currency) "
        "VALUES (:id, :v, :c, :pt, :co, :amt, :u, :cur)"
    ), {"id": _uuid(), "v": version_id, "c": category_id, "pt": policy_tier_id,
        "co": company_id, "amt": cap_value, "u": cap_unit, "cur": cap_currency})


def _seed_case(conn, *, cid: str, company_id: str, employee_id: str,
               status: str = "active",
               updated_at: str = "2026-05-01T00:00:00Z") -> None:
    conn.execute(text(
        "INSERT INTO cases (id, company_id, employee_id, status, updated_at) "
        "VALUES (:id, :co, :e, :s, :u)"
    ), {"id": cid, "co": company_id, "e": employee_id, "s": status, "u": updated_at})


def _seed_case_service(conn, *, case_id: str, category: str,
                       estimated_cost: Optional[float],
                       currency: str = "EUR", selected: bool = True,
                       service_key: Optional[str] = None) -> None:
    conn.execute(text(
        "INSERT INTO case_services (id, case_id, service_key, category, "
        "selected, estimated_cost, currency) "
        "VALUES (:id, :cid, :sk, :cat, :sel, :amt, :cur)"
    ), {"id": _uuid(), "cid": case_id, "sk": service_key or category,
        "cat": category, "sel": 1 if selected else 0,
        "amt": estimated_cost, "cur": currency})


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

class ComparisonEngineMergeTests(unittest.TestCase):
    """Pure merge logic — no DB required. Covers Notion criteria 1, 2, 3."""

    def test_partial_when_ask_exceeds_cap(self):
        # Criterion 1: housing EUR 4,200 vs cap EUR 3,500 → Partial, delta 700.
        rows = merge_caps_and_asks(
            caps=[{
                "category_code": "CAT-01",
                "category_name": "Housing Allowance",
                "cap_value": 3500.0,
                "cap_unit": "month",
                "cap_currency": "EUR",
            }],
            asks=[{"category": "housing", "estimated_cost": 4200.0,
                   "currency": "EUR"}],
            policy_version_label="v3",
            policy_effective_date="2026-01-01",
        )
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r.coverage_status, "Partial")
        self.assertEqual(r.delta, 700.0)
        self.assertEqual(r.policy_cap, 3500.0)
        self.assertEqual(r.ask_value, 4200.0)
        self.assertEqual(r.policy_version, "v3")
        self.assertEqual(r.policy_effective_date, "2026-01-01")
        self.assertFalse(r.currency_warning)

    def test_covered_when_ask_within_cap(self):
        # Criterion 2: housing EUR 3,000 vs cap EUR 3,500 → Covered, delta 0.
        rows = merge_caps_and_asks(
            caps=[{
                "category_code": "CAT-01",
                "category_name": "Housing Allowance",
                "cap_value": 3500.0,
                "cap_unit": "month",
                "cap_currency": "EUR",
            }],
            asks=[{"category": "housing", "estimated_cost": 3000.0,
                   "currency": "EUR"}],
            policy_version_label="v3",
            policy_effective_date="2026-01-01",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].coverage_status, "Covered")
        self.assertEqual(rows[0].delta, 0.0)

    def test_uncovered_when_ask_has_no_cap(self):
        # Criterion 3: ask category not in policy → Uncovered.
        rows = merge_caps_and_asks(
            caps=[],  # policy has no rows for anything
            asks=[{"category": "schools", "estimated_cost": 12000.0,
                   "currency": "EUR"}],
            policy_version_label="v3",
            policy_effective_date="2026-01-01",
        )
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r.coverage_status, "Uncovered")
        self.assertIsNone(r.policy_cap)
        self.assertEqual(r.ask_value, 12000.0)
        self.assertEqual(r.delta, 12000.0)

    def test_not_applicable_rows_are_omitted(self):
        # Neither side has anything → no row emitted.
        rows = merge_caps_and_asks(
            caps=[],
            asks=[],
            policy_version_label="v3",
            policy_effective_date="2026-01-01",
        )
        self.assertEqual(rows, [])

    def test_policy_only_row_emits_covered_zero_delta(self):
        # Policy says you have CAT-09 Tax Assistance but you haven't asked
        # for tax help in your services. Surface as Covered, delta 0.
        rows = merge_caps_and_asks(
            caps=[{
                "category_code": "CAT-09",
                "category_name": "Tax Assistance",
                "cap_value": 5000.0,
                "cap_unit": "one-time",
                "cap_currency": "EUR",
            }],
            asks=[],
            policy_version_label="v3",
            policy_effective_date="2026-01-01",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].coverage_status, "Covered")
        self.assertEqual(rows[0].delta, 0.0)
        self.assertIsNone(rows[0].ask_value)

    def test_currency_warning_when_ask_and_cap_differ(self):
        rows = merge_caps_and_asks(
            caps=[{
                "category_code": "CAT-01",
                "category_name": "Housing Allowance",
                "cap_value": 3500.0,
                "cap_unit": "month",
                "cap_currency": "EUR",
            }],
            asks=[{"category": "housing", "estimated_cost": 4200.0,
                   "currency": "USD"}],
            policy_version_label="v3",
            policy_effective_date="2026-01-01",
        )
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].currency_warning)
        # Numeric comparison happens despite the warning (no auto-conversion).
        # 4200 > 3500 → Partial, delta 700.
        self.assertEqual(rows[0].coverage_status, "Partial")
        self.assertEqual(rows[0].delta, 700.0)
        # Cap currency wins for the displayed `currency` field.
        self.assertEqual(rows[0].currency, "EUR")

    def test_delta_is_always_non_negative(self):
        rows = merge_caps_and_asks(
            caps=[{
                "category_code": "CAT-01",
                "category_name": "Housing Allowance",
                "cap_value": 3500.0,
                "cap_unit": "month",
                "cap_currency": "EUR",
            }],
            asks=[{"category": "housing", "estimated_cost": 100.0,
                   "currency": "EUR"}],
            policy_version_label="v3",
            policy_effective_date="2026-01-01",
        )
        # Covered, NOT 'delta = -3400'.
        self.assertEqual(rows[0].coverage_status, "Covered")
        self.assertEqual(rows[0].delta, 0.0)


class ComparisonEngineDBTests(unittest.TestCase):
    """End-to-end engine wiring with in-memory SQLite."""

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

        # The engine accesses `db.engine` and `db.engine.dialect`. Patch
        # both by giving the module a stub `db` whose `.engine` is ours.
        class _DB:
            pass
        self.fake_db = _DB()
        self.fake_db.engine = self.engine

    def tearDown(self):
        self.engine.dispose()

    def _bootstrap(self, *, with_case: bool = True, ask_amount: float = 4200.0,
                   ask_currency: str = "EUR"):
        company_id = _uuid()
        emp_id = _uuid()
        tier_id = _uuid()
        policy_id = _uuid()
        version_id = _uuid()

        with self.engine.begin() as conn:
            _seed_company(conn, company_id)
            _seed_employee(conn, eid=emp_id, company_id=company_id)
            _seed_tier(conn, tid=tier_id, company_id=company_id)
            _seed_employee_tier(conn, employee_id=emp_id, company_id=company_id,
                                policy_tier_id=tier_id, tier_name="Standard")
            _seed_company_policy(conn, pid=policy_id, company_id=company_id)
            _seed_version(conn, vid=version_id, policy_id=policy_id)
            cat01 = _seed_category(conn, code="CAT-01",
                                   name="Housing Allowance", sort_order=1)
            _seed_value(conn, version_id=version_id, category_id=cat01,
                        company_id=company_id, policy_tier_id=tier_id,
                        cap_value=3500.0, cap_unit="month", cap_currency="EUR")
            if with_case:
                case_id = _uuid()
                _seed_case(conn, cid=case_id, company_id=company_id,
                           employee_id=emp_id)
                _seed_case_service(conn, case_id=case_id, category="housing",
                                   estimated_cost=ask_amount,
                                   currency=ask_currency)
        return emp_id

    def test_end_to_end_partial(self):
        emp_id = self._bootstrap(ask_amount=4200.0)
        rows = compute_comparison(self.fake_db, emp_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].coverage_status, "Partial")
        self.assertEqual(rows[0].delta, 700.0)
        self.assertEqual(rows[0].category_code, "CAT-01")
        self.assertEqual(rows[0].policy_version, "v3")

    def test_end_to_end_covered(self):
        emp_id = self._bootstrap(ask_amount=3000.0)
        rows = compute_comparison(self.fake_db, emp_id)
        self.assertEqual(rows[0].coverage_status, "Covered")
        self.assertEqual(rows[0].delta, 0.0)

    def test_no_active_tier_raises(self):
        emp_id = _uuid()
        with self.engine.begin() as conn:
            _seed_company(conn, "co")
            _seed_employee(conn, eid=emp_id, company_id="co")
            # No employee_tiers row at all.
        with self.assertRaises(NoActiveTierError):
            compute_comparison(self.fake_db, emp_id)

    def test_archived_tier_does_not_count_as_active(self):
        # SQL-level guarantee: end_date IS NULL filter cannot be bypassed.
        emp_id = _uuid()
        with self.engine.begin() as conn:
            _seed_company(conn, "co")
            _seed_employee(conn, eid=emp_id, company_id="co")
            _seed_tier(conn, tid="t1", company_id="co", name="Old")
            _seed_employee_tier(conn, employee_id=emp_id, company_id="co",
                                policy_tier_id="t1", tier_name="Old",
                                end_date="2026-05-01T00:00:00Z")
        with self.assertRaises(NoActiveTierError):
            compute_comparison(self.fake_db, emp_id)

    def test_no_published_policy_raises(self):
        emp_id = _uuid()
        company_id = _uuid()
        tier_id = _uuid()
        with self.engine.begin() as conn:
            _seed_company(conn, company_id)
            _seed_employee(conn, eid=emp_id, company_id=company_id)
            _seed_tier(conn, tid=tier_id, company_id=company_id)
            _seed_employee_tier(conn, employee_id=emp_id, company_id=company_id,
                                policy_tier_id=tier_id, tier_name="Standard")
            # No company_policies + policy_versions rows.
        with self.assertRaises(NoPublishedPolicyError):
            compute_comparison(self.fake_db, emp_id)

    def test_no_case_returns_empty_list(self):
        # Per the AIQ-236 spec: no asks → every category is "Not applicable"
        # → omit them all → response is []. Distinct from NoActiveTierError
        # (the employee genuinely has a tier and a published policy; they
        # just haven't started a case yet).
        emp_id = self._bootstrap(with_case=False)
        rows = compute_comparison(self.fake_db, emp_id)
        self.assertEqual(rows, [])

    def test_case_with_no_services_selected_still_emits_policy_rows(self):
        # Employee has a case but selected no services → policy-only rows
        # still emitted (Covered, delta 0) so the policy is visible.
        emp_id = _uuid()
        company_id = _uuid()
        tier_id = _uuid()
        policy_id = _uuid()
        version_id = _uuid()
        case_id = _uuid()

        with self.engine.begin() as conn:
            _seed_company(conn, company_id)
            _seed_employee(conn, eid=emp_id, company_id=company_id)
            _seed_tier(conn, tid=tier_id, company_id=company_id)
            _seed_employee_tier(conn, employee_id=emp_id, company_id=company_id,
                                policy_tier_id=tier_id, tier_name="Standard")
            _seed_company_policy(conn, pid=policy_id, company_id=company_id)
            _seed_version(conn, vid=version_id, policy_id=policy_id)
            cat01 = _seed_category(conn, code="CAT-01",
                                   name="Housing Allowance", sort_order=1)
            _seed_value(conn, version_id=version_id, category_id=cat01,
                        company_id=company_id, policy_tier_id=tier_id,
                        cap_value=3500.0, cap_unit="month", cap_currency="EUR")
            _seed_case(conn, cid=case_id, company_id=company_id,
                       employee_id=emp_id)
            # Seed a deselected service — case exists but no asks.
            _seed_case_service(conn, case_id=case_id, category="housing",
                               estimated_cost=4200.0, currency="EUR",
                               selected=False)

        rows = compute_comparison(self.fake_db, emp_id)
        # Case exists → short-circuit doesn't fire. Selected=False filter
        # removes the ask. Cap row still emitted as Covered/0.
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].coverage_status, "Covered")
        self.assertEqual(rows[0].delta, 0.0)
        self.assertIsNone(rows[0].ask_value)


if __name__ == "__main__":
    unittest.main()
