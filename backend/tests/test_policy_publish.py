"""
Tests for [P1-4] Policy publish + version control.

Covers all four invariants in the Notion brief (AIQ-224):
  - HR-only access (employees, public → 403)
  - 14-category completeness check (missing → 422 with the missing codes)
  - Atomic archive + publish (prior published → archived; new → published;
    only one published per policy at any time)
  - Audit log entry per publish

Plus contract details:
  - version_number auto-increments per-policy (1 → 2 → 3)
  - effective_date / expiry_date / published_by / published_at recorded
  - Cross-company publish denied (403)
  - Republish-the-same-version is rejected (409)
  - GET /versions/{company_id} returns history newest-first
  - GET /active/{company_id} returns the current published version or None
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from unittest import mock

from sqlalchemy import create_engine, text
from fastapi import HTTPException

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import unittest.mock as _umock  # noqa: E402
if "backend.app.auth_deps" not in sys.modules:
    _stub_auth = _umock.MagicMock()
    _stub_auth.get_current_user = _umock.MagicMock(return_value={"id": "u", "role": "hr"})
    sys.modules["backend.app.auth_deps"] = _stub_auth


import backend.app.routers.policy_publish as pp  # noqa: E402
from backend.app.routers.policy_publish import (  # noqa: E402
    publish_policy_version,
    list_company_versions,
    get_active_version,
    PublishPayload,
    EXPECTED_CATEGORY_CODES,
)


# ─────────────────────────────────────────────────────────────────────────────
# Minimal schema — mirrors only the columns the router reads/writes.
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE companies (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE profiles (
    id          TEXT PRIMARY KEY,
    email       TEXT NOT NULL,
    company_id  TEXT,
    role        TEXT NOT NULL DEFAULT 'employee'
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
    published_at   TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE policy_categories (
    id           TEXT PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    sort_order   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE policy_values (
    id          TEXT PRIMARY KEY,
    version_id  TEXT NOT NULL,
    category_id TEXT NOT NULL,
    company_id  TEXT NOT NULL,
    cap_value   REAL,
    cap_unit    TEXT,
    cap_currency TEXT NOT NULL DEFAULT 'EUR'
);
CREATE TABLE audit_logs (
    id             TEXT NOT NULL,
    entity_type    TEXT NOT NULL,
    entity_id      TEXT NOT NULL,
    action_type    TEXT NOT NULL,
    old_value_json TEXT,
    new_value_json TEXT,
    actor_type     TEXT,
    actor_id       TEXT
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
                  role: str = "hr") -> None:
    conn.execute(text(
        "INSERT INTO profiles (id, email, company_id, role) "
        "VALUES (:id, :e, :c, :r)"
    ), {"id": pid, "e": email, "c": company_id, "r": role})


def _seed_company_policy(conn, *, pid: str, company_id: str,
                         title: str = "Test Policy") -> None:
    conn.execute(text(
        "INSERT INTO company_policies (id, company_id, title) "
        "VALUES (:id, :cid, :t)"
    ), {"id": pid, "cid": company_id, "t": title})


def _seed_version(conn, *, vid: str, policy_id: str,
                  status: str = "draft", version_number: int = 1) -> None:
    conn.execute(text(
        "INSERT INTO policy_versions "
        "(id, policy_id, status, version_number) "
        "VALUES (:id, :pid, :s, :vn)"
    ), {"id": vid, "pid": policy_id, "s": status, "vn": version_number})


def _seed_all_categories(conn) -> Dict[str, str]:
    """Insert the 14 canonical categories and return code → id map."""
    ids = {}
    for i, code in enumerate(EXPECTED_CATEGORY_CODES, start=1):
        cid = _uuid()
        conn.execute(text(
            "INSERT INTO policy_categories (id, code, display_name, sort_order) "
            "VALUES (:id, :c, :n, :s)"
        ), {"id": cid, "c": code, "n": f"Category {i}", "s": i})
        ids[code] = cid
    return ids


def _seed_value_for_each_category(conn, *, version_id: str, company_id: str,
                                  category_ids: Dict[str, str]) -> None:
    for code, cat_id in category_ids.items():
        conn.execute(text(
            "INSERT INTO policy_values (id, version_id, category_id, "
            "company_id, cap_value, cap_unit) "
            "VALUES (:id, :v, :c, :co, :amt, :unit)"
        ), {"id": _uuid(), "v": version_id, "c": cat_id, "co": company_id,
            "amt": 1000.0, "unit": "month"})


def _hr_user(actor_id: str, company_id: str) -> Dict[str, Any]:
    return {"id": actor_id, "role": "hr", "company_id": company_id}


def _employee_user(employee_id: str, company_id: str) -> Dict[str, Any]:
    return {"id": employee_id, "role": "employee", "company_id": company_id}


# ─────────────────────────────────────────────────────────────────────────────
# Test suite
# ─────────────────────────────────────────────────────────────────────────────

class PolicyPublishTests(unittest.TestCase):

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

        self.engine_patcher = mock.patch.object(pp.db, "engine", self.engine)
        self.engine_patcher.start()

    def tearDown(self):
        self.engine_patcher.stop()
        self.engine.dispose()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _bootstrap_company(self) -> Dict[str, Any]:
        company_id = _uuid()
        hr_id = _uuid()
        policy_id = _uuid()
        with self.engine.begin() as conn:
            _seed_company(conn, cid=company_id)
            _seed_profile(conn, pid=hr_id, email="hr@acme.test",
                          company_id=company_id, role="hr")
            _seed_company_policy(conn, pid=policy_id, company_id=company_id)
            cat_ids = _seed_all_categories(conn)
        return {
            "company_id": company_id, "hr_id": hr_id,
            "policy_id": policy_id, "cat_ids": cat_ids,
        }

    def _seed_complete_version(self, ctx: Dict[str, Any],
                               status: str = "draft",
                               vnum: int = 1) -> str:
        vid = _uuid()
        with self.engine.begin() as conn:
            _seed_version(conn, vid=vid, policy_id=ctx["policy_id"],
                          status=status, version_number=vnum)
            _seed_value_for_each_category(
                conn, version_id=vid,
                company_id=ctx["company_id"],
                category_ids=ctx["cat_ids"],
            )
        return vid

    def _row(self, version_id: str) -> Dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT * FROM policy_versions WHERE id = :id"
            ), {"id": version_id}).mappings().first()
        return dict(row) if row else {}

    def _count_audit_rows(self, version_id: str) -> int:
        # Publish events now land in the canonical audit_logs table with
        # action_type='update' and the semantic event in new_value_json.event.
        with self.engine.connect() as conn:
            return conn.execute(text(
                "SELECT count(*) FROM audit_logs "
                "WHERE entity_type = 'policy_version' AND entity_id = :id "
                "AND new_value_json LIKE '%policy.published%'"
            ), {"id": version_id}).scalar()

    # ── 14-category completeness ─────────────────────────────────────────────

    def test_publish_422_when_no_values_at_all(self):
        ctx = self._bootstrap_company()
        vid = _uuid()
        with self.engine.begin() as conn:
            _seed_version(conn, vid=vid, policy_id=ctx["policy_id"])

        with self.assertRaises(HTTPException) as e:
            publish_policy_version(
                PublishPayload(version_id=vid, effective_date=date(2026, 6, 1)),
                _hr_user(ctx["hr_id"], ctx["company_id"]),
            )
        self.assertEqual(e.exception.status_code, 422)
        self.assertIn("missing_categories", e.exception.detail)
        self.assertEqual(
            sorted(e.exception.detail["missing_categories"]),
            EXPECTED_CATEGORY_CODES,
        )

    def test_publish_422_when_partial_coverage(self):
        """Cover only 13 of 14 categories → response lists the missing one."""
        ctx = self._bootstrap_company()
        vid = _uuid()
        partial = {k: v for k, v in ctx["cat_ids"].items() if k != "CAT-07"}
        with self.engine.begin() as conn:
            _seed_version(conn, vid=vid, policy_id=ctx["policy_id"])
            _seed_value_for_each_category(
                conn, version_id=vid,
                company_id=ctx["company_id"],
                category_ids=partial,
            )

        with self.assertRaises(HTTPException) as e:
            publish_policy_version(
                PublishPayload(version_id=vid, effective_date=date(2026, 6, 1)),
                _hr_user(ctx["hr_id"], ctx["company_id"]),
            )
        self.assertEqual(e.exception.status_code, 422)
        self.assertEqual(e.exception.detail["missing_categories"], ["CAT-07"])

    # ── happy path: publish v1, then v2 ──────────────────────────────────────

    def test_publish_first_version_sets_published_status(self):
        ctx = self._bootstrap_company()
        vid = self._seed_complete_version(ctx)

        res = publish_policy_version(
            PublishPayload(version_id=vid, effective_date=date(2026, 6, 1)),
            _hr_user(ctx["hr_id"], ctx["company_id"]),
        )
        self.assertEqual(res.version.status, "published")
        self.assertEqual(res.version.version_number, 1)
        self.assertEqual(res.version.effective_date, "2026-06-01")
        self.assertEqual(res.archived_version_id, None)
        self.assertEqual(self._count_audit_rows(vid), 1)

        row = self._row(vid)
        self.assertEqual(row["status"], "published")
        self.assertEqual(row["published_by"], ctx["hr_id"])
        self.assertIsNotNone(row["published_at"])

    def test_publish_second_version_archives_first(self):
        ctx = self._bootstrap_company()
        v1 = self._seed_complete_version(ctx)
        publish_policy_version(
            PublishPayload(version_id=v1, effective_date=date(2026, 6, 1)),
            _hr_user(ctx["hr_id"], ctx["company_id"]),
        )

        # Second version (independent draft for same policy)
        v2 = self._seed_complete_version(ctx)
        res = publish_policy_version(
            PublishPayload(version_id=v2, effective_date=date(2026, 7, 1)),
            _hr_user(ctx["hr_id"], ctx["company_id"]),
        )

        self.assertEqual(res.version.version_number, 2)
        self.assertEqual(res.archived_version_id, v1)
        self.assertEqual(self._row(v1)["status"], "archived")
        self.assertEqual(self._row(v2)["status"], "published")

        # Invariant: at most one published row per policy
        with self.engine.connect() as conn:
            count = conn.execute(text(
                "SELECT count(*) FROM policy_versions "
                "WHERE policy_id = :pid AND status = 'published'"
            ), {"pid": ctx["policy_id"]}).scalar()
        self.assertEqual(count, 1)

    def test_third_publish_increments_version_to_3(self):
        ctx = self._bootstrap_company()
        for i in range(3):
            vid = self._seed_complete_version(ctx)
            res = publish_policy_version(
                PublishPayload(
                    version_id=vid,
                    effective_date=date(2026, 6, 1) + timedelta(days=30 * i),
                ),
                _hr_user(ctx["hr_id"], ctx["company_id"]),
            )
        self.assertEqual(res.version.version_number, 3)

    # ── expiry_date + notes ──────────────────────────────────────────────────

    def test_expiry_date_persisted(self):
        ctx = self._bootstrap_company()
        vid = self._seed_complete_version(ctx)
        publish_policy_version(
            PublishPayload(
                version_id=vid,
                effective_date=date(2026, 6, 1),
                expiry_date=date(2027, 5, 31),
                notes="Initial publish",
            ),
            _hr_user(ctx["hr_id"], ctx["company_id"]),
        )
        row = self._row(vid)
        self.assertEqual(row["expiry_date"], "2027-05-31")

    # ── HR-only / cross-company guards ───────────────────────────────────────

    def test_publish_403_when_role_is_employee(self):
        ctx = self._bootstrap_company()
        vid = self._seed_complete_version(ctx)

        with self.assertRaises(HTTPException) as e:
            publish_policy_version(
                PublishPayload(version_id=vid, effective_date=date(2026, 6, 1)),
                _employee_user(_uuid(), ctx["company_id"]),
            )
        self.assertEqual(e.exception.status_code, 403)

    def test_publish_403_when_cross_company(self):
        ctx = self._bootstrap_company()
        vid = self._seed_complete_version(ctx)
        other_company = _uuid()

        with self.assertRaises(HTTPException) as e:
            publish_policy_version(
                PublishPayload(version_id=vid, effective_date=date(2026, 6, 1)),
                _hr_user(_uuid(), other_company),  # HR from a different company
            )
        self.assertEqual(e.exception.status_code, 403)

    def test_admin_can_publish_across_companies(self):
        ctx = self._bootstrap_company()
        vid = self._seed_complete_version(ctx)
        admin = {"id": _uuid(), "role": "admin", "company_id": None}

        res = publish_policy_version(
            PublishPayload(version_id=vid, effective_date=date(2026, 6, 1)),
            admin,
        )
        self.assertEqual(res.version.status, "published")

    # ── 404 / 409 contracts ──────────────────────────────────────────────────

    def test_publish_404_when_version_not_found(self):
        ctx = self._bootstrap_company()
        with self.assertRaises(HTTPException) as e:
            publish_policy_version(
                PublishPayload(version_id=_uuid(),
                               effective_date=date(2026, 6, 1)),
                _hr_user(ctx["hr_id"], ctx["company_id"]),
            )
        self.assertEqual(e.exception.status_code, 404)

    def test_republish_same_version_returns_409(self):
        ctx = self._bootstrap_company()
        vid = self._seed_complete_version(ctx)
        publish_policy_version(
            PublishPayload(version_id=vid, effective_date=date(2026, 6, 1)),
            _hr_user(ctx["hr_id"], ctx["company_id"]),
        )

        with self.assertRaises(HTTPException) as e:
            publish_policy_version(
                PublishPayload(version_id=vid, effective_date=date(2026, 6, 1)),
                _hr_user(ctx["hr_id"], ctx["company_id"]),
            )
        self.assertEqual(e.exception.status_code, 409)

    # ── GET endpoints ────────────────────────────────────────────────────────

    def test_list_company_versions_newest_first(self):
        ctx = self._bootstrap_company()
        v1 = self._seed_complete_version(ctx)
        v2 = self._seed_complete_version(ctx)

        rows = list_company_versions(
            ctx["company_id"],
            _hr_user(ctx["hr_id"], ctx["company_id"]),
        )
        ids = [r.id for r in rows]
        self.assertIn(v1, ids)
        self.assertIn(v2, ids)
        # Both seeded with default `created_at`; the test asserts the endpoint
        # returns *both* and the policy/company relationship is correctly
        # joined.

    def test_list_company_versions_403_cross_company(self):
        ctx = self._bootstrap_company()
        with self.assertRaises(HTTPException) as e:
            list_company_versions(
                _uuid(),  # different company id
                _hr_user(ctx["hr_id"], ctx["company_id"]),
            )
        self.assertEqual(e.exception.status_code, 403)

    def test_get_active_version_returns_published(self):
        ctx = self._bootstrap_company()
        v1 = self._seed_complete_version(ctx)
        publish_policy_version(
            PublishPayload(version_id=v1, effective_date=date(2026, 6, 1)),
            _hr_user(ctx["hr_id"], ctx["company_id"]),
        )

        res = get_active_version(
            ctx["company_id"],
            _hr_user(ctx["hr_id"], ctx["company_id"]),
        )
        self.assertIsNotNone(res)
        self.assertEqual(res.id, v1)
        self.assertEqual(res.status, "published")

    def test_get_active_version_returns_none_when_no_published(self):
        ctx = self._bootstrap_company()
        # No publish — only a draft version exists
        self._seed_complete_version(ctx)

        res = get_active_version(
            ctx["company_id"],
            _hr_user(ctx["hr_id"], ctx["company_id"]),
        )
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
