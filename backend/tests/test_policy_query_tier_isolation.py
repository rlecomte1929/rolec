"""
Tests for [P5-9 C1] tier isolation in policy retrieval.

The migration ``20260522160000_canonical_policy_facts_tier.sql`` added a
``tier`` column to ``canonical_policy_facts``. The retrieval path in
``backend/services/policy_query_answering.py`` now forwards a
``caller_tier`` value to ``list_canonical_policy_facts`` so a Manager-tier
employee cannot retrieve Executive-tier benefit values.

These tests pin the contract:
  1. Caller tier = "Manager" → Executive-tagged facts are excluded;
     Manager facts + universal (NULL) facts are returned.
  2. Caller tier = None (HR/admin) → all facts are returned, regardless
     of tier.
  3. Caller tier = "__NO_TIER__" (employee with no active assignment)
     → only universal (NULL) facts are returned.
  4. `_resolve_caller_tier` looks up the active ``employee_tiers`` row
     for non-HR users.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from typing import Any, Dict, List, Optional
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# We exercise the DB layer directly + the resolver helper. The full
# `answer_company_scoped_policy_query` path requires the LLM client and
# is covered by other tests; here we focus on the tier-isolation
# contract specifically.
from backend.app.services.policy_query_answering import (  # noqa: E402
    _resolve_caller_tier,
)


# ─────────────────────────────────────────────────────────────────────────────
# Minimal SQLite schema mirroring the bits of canonical_policy_facts +
# employee_tiers the tier-isolation code touches.
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE canonical_policy_facts (
    id              TEXT PRIMARY KEY,
    canonical_policy_document_id TEXT NOT NULL,
    company_id      TEXT NOT NULL,
    tier            TEXT,                -- NULL = universal
    value_type      TEXT NOT NULL,
    eligibility_json     TEXT NOT NULL DEFAULT '{}',
    assignment_types_json TEXT NOT NULL DEFAULT '[]',
    raw_payload_json     TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE employee_tiers (
    id              TEXT PRIMARY KEY,
    employee_id     TEXT NOT NULL,
    company_id      TEXT NOT NULL,
    policy_tier_id  TEXT NOT NULL,
    tier_name       TEXT NOT NULL,
    assigned_by     TEXT,
    assigned_at     TEXT NOT NULL,
    end_date        TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _uuid() -> str:
    return str(uuid.uuid4())


def _seed_fact(conn, *, fid: str, doc_id: str, company_id: str,
               tier: Optional[str], value_type: str = "amount") -> None:
    conn.execute(text(
        "INSERT INTO canonical_policy_facts "
        "(id, canonical_policy_document_id, company_id, tier, value_type) "
        "VALUES (:id, :doc, :co, :tier, :vt)"
    ), {"id": fid, "doc": doc_id, "co": company_id, "tier": tier, "vt": value_type})


def _seed_employee_tier(conn, *, employee_id: str, company_id: str,
                        tier_name: str, end_date: Optional[str] = None) -> None:
    conn.execute(text(
        "INSERT INTO employee_tiers "
        "(id, employee_id, company_id, policy_tier_id, tier_name, "
        " assigned_by, assigned_at, end_date) "
        "VALUES (:id, :eid, :co, :pt, :tn, :ab, :at, :ed)"
    ), {
        "id": _uuid(), "eid": employee_id, "co": company_id,
        "pt": _uuid(), "tn": tier_name, "ab": _uuid(),
        "at": "2026-05-22T00:00:00Z", "ed": end_date,
    })


class _FakeDb:
    """Lightweight Database-shaped wrapper that exposes the same `engine`
    attribute and the list_canonical_policy_facts implementation we're
    testing. Mirrors the real DB query in backend/database.py."""

    def __init__(self, engine):
        self.engine = engine

    def list_canonical_policy_facts(
        self,
        document_id: str,
        *,
        company_id: Optional[str] = None,
        tier: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        sql = (
            "SELECT * FROM canonical_policy_facts "
            "WHERE canonical_policy_document_id = :id"
        )
        params: Dict[str, Any] = {"id": document_id}
        if company_id:
            sql += " AND company_id = :company_id"
            params["company_id"] = company_id
        # [P5-9 C1] tier filter — mirrors backend/database.py
        if tier is not None:
            sql += " AND (tier IS NULL OR tier = :tier_filter)"
            params["tier_filter"] = tier
        sql += " ORDER BY created_at ASC"
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Test suite
# ─────────────────────────────────────────────────────────────────────────────

class PolicyTierIsolationTests(unittest.TestCase):

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
        self.db = _FakeDb(self.engine)
        self.doc_id = _uuid()
        self.company_id = _uuid()

        # Seed three facts: one universal, one Manager-only, one Executive-only.
        with self.engine.begin() as conn:
            _seed_fact(conn, fid=_uuid(), doc_id=self.doc_id,
                       company_id=self.company_id, tier=None)        # universal
            _seed_fact(conn, fid=_uuid(), doc_id=self.doc_id,
                       company_id=self.company_id, tier="Manager")   # manager
            _seed_fact(conn, fid=_uuid(), doc_id=self.doc_id,
                       company_id=self.company_id, tier="Executive") # executive

    def tearDown(self):
        self.engine.dispose()

    # ── DB-level filter contract ─────────────────────────────────────────────

    def test_manager_caller_sees_universal_and_manager_only(self):
        facts = self.db.list_canonical_policy_facts(
            self.doc_id, company_id=self.company_id, tier="Manager",
        )
        tiers = {f.get("tier") for f in facts}
        self.assertIn(None, tiers, "universal facts must be returned")
        self.assertIn("Manager", tiers, "matching-tier facts must be returned")
        self.assertNotIn(
            "Executive", tiers,
            "Executive-only facts MUST NOT leak to Manager-tier caller",
        )

    def test_executive_caller_sees_universal_and_executive_only(self):
        facts = self.db.list_canonical_policy_facts(
            self.doc_id, company_id=self.company_id, tier="Executive",
        )
        tiers = {f.get("tier") for f in facts}
        self.assertIn(None, tiers)
        self.assertIn("Executive", tiers)
        self.assertNotIn("Manager", tiers)

    def test_none_tier_returns_all_for_admin_or_hr(self):
        facts = self.db.list_canonical_policy_facts(
            self.doc_id, company_id=self.company_id, tier=None,
        )
        tiers = {f.get("tier") for f in facts}
        self.assertEqual(tiers, {None, "Manager", "Executive"})

    def test_no_tier_sentinel_returns_only_universal(self):
        """Employee with no active employee_tiers row → '__NO_TIER__'
        sentinel matches no real tier name → only universal (NULL) facts."""
        facts = self.db.list_canonical_policy_facts(
            self.doc_id, company_id=self.company_id, tier="__NO_TIER__",
        )
        tiers = {f.get("tier") for f in facts}
        self.assertEqual(tiers, {None})

    def test_unknown_tier_returns_only_universal(self):
        """A tier name that doesn't match any seeded row → only universals."""
        facts = self.db.list_canonical_policy_facts(
            self.doc_id, company_id=self.company_id, tier="Ghost-Tier",
        )
        tiers = {f.get("tier") for f in facts}
        self.assertEqual(tiers, {None})

    # ── resolver contract ────────────────────────────────────────────────────

    def test_resolver_returns_none_for_hr(self):
        self.assertIsNone(
            _resolve_caller_tier(self.db, user_id=_uuid(), user_role="hr"),
        )

    def test_resolver_returns_none_for_admin(self):
        self.assertIsNone(
            _resolve_caller_tier(self.db, user_id=_uuid(), user_role="admin"),
        )

    def test_resolver_returns_tier_name_for_employee_with_active_row(self):
        emp_id = _uuid()
        with self.engine.begin() as conn:
            _seed_employee_tier(
                conn, employee_id=emp_id, company_id=self.company_id,
                tier_name="Manager",
            )
        self.assertEqual(
            _resolve_caller_tier(self.db, user_id=emp_id, user_role="employee"),
            "Manager",
        )

    def test_resolver_returns_sentinel_for_employee_without_active_row(self):
        # Employee exists in employee_tiers but the row is archived.
        emp_id = _uuid()
        with self.engine.begin() as conn:
            _seed_employee_tier(
                conn, employee_id=emp_id, company_id=self.company_id,
                tier_name="Manager", end_date="2026-04-01T00:00:00Z",
            )
        self.assertEqual(
            _resolve_caller_tier(self.db, user_id=emp_id, user_role="employee"),
            "__NO_TIER__",
        )

    def test_resolver_returns_sentinel_when_no_employee_tiers_row(self):
        # Employee has zero rows in employee_tiers (never been assigned).
        self.assertEqual(
            _resolve_caller_tier(self.db, user_id=_uuid(), user_role="employee"),
            "__NO_TIER__",
        )

    def test_resolver_falls_back_to_sentinel_on_db_error(self):
        """A failing DB query must NOT return None (which would skip the
        filter) — fail-closed to __NO_TIER__ so only universals leak."""
        broken_db = _FakeDb(mock.MagicMock())
        broken_db.engine.connect.side_effect = RuntimeError("db down")
        self.assertEqual(
            _resolve_caller_tier(broken_db, user_id=_uuid(), user_role="employee"),
            "__NO_TIER__",
        )


if __name__ == "__main__":
    unittest.main()
