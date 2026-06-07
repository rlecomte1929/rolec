"""
Tests for backend/app/routers/ai_decisions.py (AI-006).

Mirrors the pattern in test_exception_requests_router.py: in-memory SQLite
engine with the ai_decisions + audit_logs schemas preloaded, router
functions called directly (bypasses FastAPI's dependency injection so the
tests stay independent of the rest of the wiring).

One adaptation: the production router uses `CAST(:ai_output AS jsonb)`,
which Postgres needs but SQLite does not understand. A
`before_cursor_execute` listener strips that cast for the SQLite engine
so the same router code exercises the same path. The stored value is a
JSON-encoded string in SQLite, decoded inside tests where the shape
matters.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest
import uuid
from unittest import mock

from sqlalchemy import create_engine, event, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import ai_decisions as router_module  # noqa: E402
from backend.app.routers.ai_decisions import (  # noqa: E402
    AIDecisionCreate,
    create_ai_decision,
    list_ai_decisions,
)
from backend.app.auth_deps import require_admin_or_hr  # noqa: E402
from fastapi import HTTPException  # noqa: E402


SCHEMA = """
CREATE TABLE ai_decisions (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  actor_id TEXT,
  company_id TEXT,
  feature TEXT NOT NULL,
  recommendation_id TEXT NOT NULL,
  ai_output TEXT NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('accept', 'override', 'reject')),
  reason TEXT,
  outcome TEXT
);
CREATE TABLE audit_logs (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  old_value_json TEXT,
  new_value_json TEXT,
  actor_type TEXT NOT NULL,
  actor_id TEXT,
  created_at TEXT
);
"""

# Rewrite `CAST(? AS jsonb)` → `?` so the production SQL runs on SQLite.
_JSONB_CAST_RE = re.compile(r"CAST\s*\(\s*(\?|\:\w+)\s+AS\s+jsonb\s*\)", re.IGNORECASE)


def _make_user(uid: str, role: str, company_id: str | None, is_admin: bool = False):
    return {
        "id": uid,
        "role": role,
        "company": company_id,
        "is_admin": is_admin,
    }


class AIDecisionsRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )

        @event.listens_for(self.engine, "before_cursor_execute", retval=True)
        def _strip_jsonb_cast(conn, cursor, statement, parameters, context, executemany):
            new_statement = _JSONB_CAST_RE.sub(r"\1", statement)
            return new_statement, parameters

        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))

        self.engine_patcher = mock.patch.object(router_module.db, "engine", self.engine)
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)
        # _caller_company_id falls back to get_profile_record when user["company"]
        # is None — return None so we exercise both code paths cleanly.
        self.profile_patcher = mock.patch.object(
            router_module.db,
            "get_profile_record",
            side_effect=lambda uid: {"id": uid, "company_id": None},
        )
        self.profile_patcher.start()
        self.addCleanup(self.profile_patcher.stop)
        # UIAUDIT-G6: _caller_company_id now resolves hr_users FIRST. Default it to
        # None so the existing tests exercise the profile / user.company fallback
        # cleanly (and don't query a non-existent hr_users table in the sqlite mirror).
        self.hr_company_patcher = mock.patch.object(
            router_module.db, "get_hr_company_id", return_value=None,
        )
        self.hr_company_patcher.start()
        self.addCleanup(self.hr_company_patcher.stop)

    def _rows(self):
        with self.engine.connect() as conn:
            return list(
                conn.execute(
                    text("SELECT * FROM ai_decisions ORDER BY rowid")
                ).mappings()
            )

    def _audit_rows(self):
        with self.engine.connect() as conn:
            return list(
                conn.execute(
                    text(
                        "SELECT entity_type, entity_id, action_type, actor_id "
                        "FROM audit_logs ORDER BY rowid"
                    )
                ).mappings()
            )

    # ------------------------------------------------------------------
    # UIAUDIT-G6 — company resolution (hr_users-first for legacy/text HR ids)
    # ------------------------------------------------------------------
    def test_caller_company_id_resolves_via_hr_users(self):
        # Legacy/text HR id (e.g. seed-hr-testingapril): no user.company, profile
        # company_id is NULL, but hr_users links them — must resolve, not 403.
        user = _make_user("seed-hr-testingapril", "hr", None)
        with mock.patch.object(
            router_module.db, "get_hr_company_id", return_value="c0000000-0000-0000-0000-000000000001"
        ):
            self.assertEqual(
                router_module._caller_company_id(user),
                "c0000000-0000-0000-0000-000000000001",
            )

    def test_caller_company_id_falls_back_to_profile(self):
        # When hr_users has nothing, fall back to the profile company_id.
        user = _make_user("uuid-hr", "hr", None)
        with mock.patch.object(router_module.db, "get_hr_company_id", return_value=None), \
             mock.patch.object(
                 router_module.db, "get_profile_record",
                 return_value={"id": "uuid-hr", "company_id": "comp-via-profile"},
             ):
            self.assertEqual(router_module._caller_company_id(user), "comp-via-profile")

    # ------------------------------------------------------------------
    # POST /api/ai/decisions
    # ------------------------------------------------------------------
    def test_accept_without_reason_is_allowed(self) -> None:
        hr = _make_user(str(uuid.uuid4()), "HR", "company-a")
        body = AIDecisionCreate(
            feature="exception_insight",
            recommendation_id="rec-1",
            ai_output={"summary": "73% precedent"},
            decision="accept",
        )

        result = create_ai_decision(body=body, user=hr)

        self.assertEqual(result["decision"], "accept")
        self.assertIsNone(result["reason"])
        self.assertEqual(result["feature"], "exception_insight")
        self.assertEqual(result["company_id"], "company-a")
        self.assertEqual(result["actor_id"], hr["id"])

        # Audit row written
        audit = self._audit_rows()
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["entity_type"], "ai_decisions")
        self.assertEqual(audit[0]["action_type"], "insert")
        self.assertEqual(audit[0]["actor_id"], hr["id"])

    def test_override_with_reason_is_allowed(self) -> None:
        hr = _make_user(str(uuid.uuid4()), "HR", "company-a")
        body = AIDecisionCreate(
            feature="exception_insight",
            recommendation_id="rec-2",
            ai_output={"summary": "low confidence"},
            decision="override",
            reason="Manager has direct knowledge of this case.",
        )

        result = create_ai_decision(body=body, user=hr)

        self.assertEqual(result["decision"], "override")
        self.assertEqual(result["reason"], "Manager has direct knowledge of this case.")

        # ai_output payload round-trips
        stored = json.loads(result["ai_output"]) if isinstance(result["ai_output"], str) else result["ai_output"]
        self.assertEqual(stored, {"summary": "low confidence"})

    def test_override_without_reason_is_rejected(self) -> None:
        hr = _make_user(str(uuid.uuid4()), "HR", "company-a")
        body = AIDecisionCreate(
            feature="exception_insight",
            recommendation_id="rec-3",
            ai_output={},
            decision="override",
            reason=None,
        )

        with self.assertRaises(HTTPException) as ctx:
            create_ai_decision(body=body, user=hr)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("override", ctx.exception.detail.lower())

        # No row written, no audit
        self.assertEqual(len(self._rows()), 0)
        self.assertEqual(len(self._audit_rows()), 0)

    def test_reject_without_reason_is_rejected(self) -> None:
        hr = _make_user(str(uuid.uuid4()), "HR", "company-a")
        body = AIDecisionCreate(
            feature="exception_insight",
            recommendation_id="rec-4",
            ai_output={},
            decision="reject",
            reason="   ",  # whitespace-only must also be rejected
        )

        with self.assertRaises(HTTPException) as ctx:
            create_ai_decision(body=body, user=hr)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("reject", ctx.exception.detail.lower())

    # ------------------------------------------------------------------
    # Auth dependency — role gate
    # ------------------------------------------------------------------
    def test_employee_blocked_by_role_dep(self) -> None:
        """The router relies on require_admin_or_hr to 403 employees.
        Unit-test the dep directly since the function body never sees the
        request from an unauthorised role."""
        emp = _make_user(str(uuid.uuid4()), "EMPLOYEE", "company-a", is_admin=False)
        with self.assertRaises(HTTPException) as ctx:
            require_admin_or_hr(user=emp)
        self.assertEqual(ctx.exception.status_code, 403)

    # ------------------------------------------------------------------
    # GET /api/ai/decisions
    # ------------------------------------------------------------------
    def _seed_three_decisions(self, company: str, hr: dict):
        for spec in [
            ("exception_insight", "rec-a", "accept", None),
            ("exception_insight", "rec-b", "override", "doesn't fit"),
            ("assignment_match", "rec-c", "reject", "wrong corridor"),
        ]:
            feature, rec_id, decision, reason = spec
            create_ai_decision(
                body=AIDecisionCreate(
                    feature=feature,
                    recommendation_id=rec_id,
                    ai_output={"k": rec_id},
                    decision=decision,
                    reason=reason,
                ),
                user=hr,
            )

    # NOTE on Query(None) defaults: when `list_ai_decisions` is called directly
    # (as opposed to via a FastAPI request), the `Query(...)` defaults remain
    # as FastAPI Query objects rather than being unwrapped to None. To keep
    # the tests honest about what they exercise we always pass all kwargs
    # explicitly.

    def test_list_filter_by_feature(self) -> None:
        hr = _make_user(str(uuid.uuid4()), "HR", "company-a")
        self._seed_three_decisions("company-a", hr)

        result = list_ai_decisions(user=hr, feature="exception_insight", decision=None, limit=100)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(r["feature"] == "exception_insight" for r in result))

        result = list_ai_decisions(user=hr, feature="assignment_match", decision=None, limit=100)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["recommendation_id"], "rec-c")

    def test_list_filter_by_decision(self) -> None:
        hr = _make_user(str(uuid.uuid4()), "HR", "company-a")
        self._seed_three_decisions("company-a", hr)

        result = list_ai_decisions(user=hr, feature=None, decision="override", limit=100)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["decision"], "override")

        result = list_ai_decisions(user=hr, feature=None, decision="accept", limit=100)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["decision"], "accept")

    def test_list_scoped_by_company(self) -> None:
        hr_a = _make_user(str(uuid.uuid4()), "HR", "company-a")
        hr_b = _make_user(str(uuid.uuid4()), "HR", "company-b")
        self._seed_three_decisions("company-a", hr_a)
        # One decision for company-b
        create_ai_decision(
            body=AIDecisionCreate(
                feature="exception_insight",
                recommendation_id="rec-b1",
                ai_output={},
                decision="accept",
            ),
            user=hr_b,
        )

        a_view = list_ai_decisions(user=hr_a, feature=None, decision=None, limit=100)
        b_view = list_ai_decisions(user=hr_b, feature=None, decision=None, limit=100)
        self.assertEqual(len(a_view), 3)
        self.assertEqual(len(b_view), 1)
        self.assertTrue(all(r["company_id"] == "company-a" for r in a_view))
        self.assertTrue(all(r["company_id"] == "company-b" for r in b_view))

    def test_list_admin_without_company_sees_all(self) -> None:
        """Admin-without-linked-company is the documented cross-tenant audit role."""
        hr_a = _make_user(str(uuid.uuid4()), "HR", "company-a")
        hr_b = _make_user(str(uuid.uuid4()), "HR", "company-b")
        self._seed_three_decisions("company-a", hr_a)
        create_ai_decision(
            body=AIDecisionCreate(
                feature="exception_insight",
                recommendation_id="rec-b1",
                ai_output={},
                decision="accept",
            ),
            user=hr_b,
        )

        admin_no_company = _make_user(
            str(uuid.uuid4()), "ADMIN", company_id=None, is_admin=True
        )
        admin_view = list_ai_decisions(
            user=admin_no_company, feature=None, decision=None, limit=100
        )
        self.assertEqual(len(admin_view), 4)
        companies = {r["company_id"] for r in admin_view}
        self.assertEqual(companies, {"company-a", "company-b"})


if __name__ == "__main__":
    unittest.main()
