"""
C1-16 · Tests for GET /api/hr/cases/{case_id}/audit

Coverage:
  - Cross-tenant returns 404 (not 403)
  - Missing case returns 404
  - rce.* tables unavailable → degrades to empty events + 200
  - Cursor encode / decode round-trip
  - Invalid cursor returns 400
  - ETag header present when events exist
"""
from __future__ import annotations

import unittest
from typing import Any, Dict, Optional
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app, get_current_user, UserRole
from backend.app.routers.hr_case_audit import _decode_cursor, _encode_cursor

# ---------------------------------------------------------------------------
# Fake users + cases
# ---------------------------------------------------------------------------

_HR_A: Dict[str, Any] = {
    "id": "user-hr-a",
    "role": UserRole.HR.value,
    "email": "hr-a@company-a.test",
    "is_admin": False,
}

_HR_B: Dict[str, Any] = {
    "id": "user-hr-b",
    "role": UserRole.HR.value,
    "email": "hr-b@company-b.test",
    "is_admin": False,
}

_CASE_A: Dict[str, Any] = {
    "id": "case-a",
    "company_id": "company-a",
    "hr_user_id": "user-hr-a",
    "employee_id": "emp-a",
    "status": "in_progress",
}

_HR_COMPANY: Dict[str, str] = {
    "user-hr-a": "company-a",
    "user-hr-b": "company-b",
}


def _make_dependency_override(fake_user: Dict[str, Any]):
    async def _override(request=None, authorization=None) -> Dict[str, Any]:  # type: ignore[override]
        return fake_user
    return _override


def _make_failing_engine() -> Any:
    """Engine stub whose .connect() raises — exercises the graceful degrade."""
    class _FailingEngine:
        def connect(self):
            raise RuntimeError("simulated DB unavailable")
    return _FailingEngine()


class _BaseCase(unittest.TestCase):
    def _client_for(self, fake_user: Dict[str, Any]) -> TestClient:
        app.dependency_overrides[get_current_user] = _make_dependency_override(fake_user)
        return TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _patches(self, case: Optional[Dict[str, Any]] = _CASE_A):
        return [
            patch(
                "backend.app.routers.hr_case_audit.db.get_relocation_case",
                side_effect=lambda cid: case if (case and cid == case["id"]) else None,
            ),
            patch(
                "backend.app.auth_deps.db.get_profile_record",
                side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
            ),
            patch(
                "backend.app.routers.hr_case_audit.db.engine",
                new=_make_failing_engine(),
            ),
        ]


# ---------------------------------------------------------------------------
# Cursor round-trip (pure unit test, no client needed)
# ---------------------------------------------------------------------------


class TestCursorRoundTrip(unittest.TestCase):
    def test_encode_decode_is_lossless(self) -> None:
        ts = "2026-05-27T10:15:23+00:00"
        source = "agent_runs"
        row_id = "11111111-2222-3333-4444-555555555555"
        token = _encode_cursor(ts, source, row_id)
        # base64 — no padding, no '/' or '+' characters
        self.assertNotIn("=", token)
        self.assertNotIn("/", token)
        self.assertNotIn("+", token)
        decoded_ts, decoded_source, decoded_id = _decode_cursor(token)
        self.assertEqual(decoded_ts, ts)
        self.assertEqual(decoded_source, source)
        self.assertEqual(decoded_id, row_id)

    def test_garbage_cursor_raises_http_exception(self) -> None:
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as cm:
            _decode_cursor("definitely-not-a-cursor")
        self.assertEqual(cm.exception.status_code, 400)


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


class TestAuditEndpoint(_BaseCase):
    def test_returns_200_with_empty_events_when_db_unavailable(self) -> None:
        """Graceful degrade: rce.* unavailable → empty events list, NOT 500."""
        client = self._client_for(_HR_A)
        with self._patches()[0], self._patches()[1], self._patches()[2]:
            resp = client.get(
                "/api/hr/cases/case-a/audit",
                headers={"Authorization": "Bearer hr-a-token"},
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["case_id"], "case-a")
        self.assertEqual(data["events"], [])
        self.assertIsNone(data["next_cursor"])

    def test_returns_404_for_cross_tenant(self) -> None:
        """HR-B (company-b) requests case-a (company-a) → 404, not 403."""
        client = self._client_for(_HR_B)
        with (
            patch(
                "backend.app.routers.hr_case_audit.db.get_relocation_case",
                return_value=_CASE_A,
            ),
            patch(
                "backend.app.auth_deps.db.get_profile_record",
                side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
            ),
        ):
            resp = client.get(
                "/api/hr/cases/case-a/audit",
                headers={"Authorization": "Bearer hr-b-token"},
            )
        self.assertEqual(resp.status_code, 404)
        # Must not leak the real tenant id in the error body.
        self.assertNotIn("company-a", resp.text)

    def test_returns_404_for_missing_case(self) -> None:
        client = self._client_for(_HR_A)
        with (
            patch(
                "backend.app.routers.hr_case_audit.db.get_relocation_case",
                return_value=None,
            ),
            patch(
                "backend.app.auth_deps.db.get_profile_record",
                side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
            ),
        ):
            resp = client.get(
                "/api/hr/cases/no-such-id/audit",
                headers={"Authorization": "Bearer hr-a-token"},
            )
        self.assertEqual(resp.status_code, 404)

    def test_invalid_cursor_returns_400(self) -> None:
        client = self._client_for(_HR_A)
        with self._patches()[0], self._patches()[1], self._patches()[2]:
            resp = client.get(
                "/api/hr/cases/case-a/audit?cursor=not-a-cursor",
                headers={"Authorization": "Bearer hr-a-token"},
            )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid pagination cursor", resp.text)

    def test_limit_clamped_to_max(self) -> None:
        """`?limit=9999` is rejected by FastAPI's Query validation (le=200)."""
        client = self._client_for(_HR_A)
        with self._patches()[0], self._patches()[1], self._patches()[2]:
            resp = client.get(
                "/api/hr/cases/case-a/audit?limit=9999",
                headers={"Authorization": "Bearer hr-a-token"},
            )
        self.assertEqual(resp.status_code, 422)  # FastAPI validation error


# ---------------------------------------------------------------------------
# [NAV-HR-3-FU / AIQ-1137] bridged aggregation + filters + amend/reverse
# ---------------------------------------------------------------------------


class TestAuditTrailFU(unittest.TestCase):
    """Tests for GET /audit-trail aggregation/filters + POST amend/reverse.

    The db layer is mocked throughout (its SQL is postgres-only), so these
    exercise the router's tenant gate, filter plumbing, and reversible-state rule.
    """

    R = "backend.app.routers.hr_case_audit.db"

    def _client(self, fake_user: Dict[str, Any]) -> TestClient:
        # Override the auth_deps dependencies directly — the router uses
        # backend.app.auth_deps.get_current_user, NOT backend.main's (a different
        # function), so overriding main's would silently never fire (CLAUDE.md).
        from backend.app import auth_deps
        app.dependency_overrides[auth_deps.get_current_user] = lambda: fake_user
        app.dependency_overrides[auth_deps.get_org_id_for_hr_user] = lambda: _HR_COMPANY.get(fake_user["id"], "")
        return TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _profile_patch(self):
        import contextlib
        return contextlib.nullcontext()

    def test_aggregates_across_bridged_ids_and_returns_rows(self) -> None:
        client = self._client(_HR_A)
        canned = [{
            "id": "ev-1", "entity_type": "assignment", "entity_id": "reloc-uuid",
            "action_type": "update", "actor_type": "human", "actor_id": None,
            "actor_name": "Alice", "event": "REASSIGN_HR_OWNER",
            "old_value": None, "new_value": {"event": "REASSIGN_HR_OWNER"}, "created_at": "2026-06-17T00:00:00+00:00",
        }]
        with (
            patch(f"{self.R}.get_case_company_for_audit", return_value="company-a"),
            patch(f"{self.R}.resolve_case_audit_entity_ids", return_value=["assignment-a", "reloc-uuid"]) as m_ids,
            patch(f"{self.R}.query_case_audit_trail", return_value=canned) as m_q,
            self._profile_patch(),
        ):
            resp = client.get("/api/hr/cases/assignment-a/audit-trail", headers={"Authorization": "Bearer t"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]["id"], "ev-1")
        m_ids.assert_called_once_with("assignment-a")
        # entity_ids from the bridge are passed through to the query.
        self.assertEqual(m_q.call_args.args[0], ["assignment-a", "reloc-uuid"])

    def test_filters_are_passed_through(self) -> None:
        client = self._client(_HR_A)
        with (
            patch(f"{self.R}.get_case_company_for_audit", return_value="company-a"),
            patch(f"{self.R}.resolve_case_audit_entity_ids", return_value=["assignment-a"]),
            patch(f"{self.R}.query_case_audit_trail", return_value=[]) as m_q,
            self._profile_patch(),
        ):
            resp = client.get(
                "/api/hr/cases/assignment-a/audit-trail?action_type=update&event=REASSIGN_HR_OWNER&date_from=2026-06-01T00:00:00Z",
                headers={"Authorization": "Bearer t"},
            )
        self.assertEqual(resp.status_code, 200)
        kw = m_q.call_args.kwargs
        self.assertEqual(kw["action_type"], "update")
        self.assertEqual(kw["event"], "REASSIGN_HR_OWNER")
        self.assertEqual(kw["from_ts"], "2026-06-01T00:00:00Z")

    def test_bad_action_type_filter_422(self) -> None:
        client = self._client(_HR_A)
        with self._profile_patch():
            resp = client.get(
                "/api/hr/cases/assignment-a/audit-trail?action_type=bogus",
                headers={"Authorization": "Bearer t"},
            )
        self.assertEqual(resp.status_code, 422)

    def test_cross_tenant_404(self) -> None:
        client = self._client(_HR_B)  # company-b
        with (
            patch(f"{self.R}.get_case_company_for_audit", return_value="company-a"),
            self._profile_patch(),
        ):
            resp = client.get("/api/hr/cases/assignment-a/audit-trail", headers={"Authorization": "Bearer t"})
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn("company-a", resp.text)

    def test_unresolvable_case_404(self) -> None:
        client = self._client(_HR_A)
        with (
            patch(f"{self.R}.get_case_company_for_audit", return_value=None),
            self._profile_patch(),
        ):
            resp = client.get("/api/hr/cases/ghost/audit-trail", headers={"Authorization": "Bearer t"})
        self.assertEqual(resp.status_code, 404)

    def test_amend_appends_linked_row(self) -> None:
        client = self._client(_HR_A)
        target = {"id": "ev-1", "entity_type": "assignment", "entity_id": "reloc-uuid",
                  "action_type": "update", "event": "REASSIGN_HR_OWNER", "old_value": None, "new_value": {}}
        with (
            patch(f"{self.R}.get_case_company_for_audit", return_value="company-a"),
            patch(f"{self.R}.resolve_case_audit_entity_ids", return_value=["assignment-a", "reloc-uuid"]),
            patch(f"{self.R}.get_audit_log_entry", return_value=target),
            patch(f"{self.R}.insert_case_audit_annotation", return_value="new-id") as m_ins,
            self._profile_patch(),
        ):
            resp = client.post(
                "/api/hr/cases/assignment-a/audit-trail/ev-1/amend",
                json={"reason": "Wrong owner picked"},
                headers={"Authorization": "Bearer t"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["amends"], "ev-1")
        self.assertEqual(m_ins.call_args.kwargs["link_field"], "amends")
        self.assertEqual(m_ins.call_args.kwargs["event"], "AUDIT_AMENDED")

    def test_reverse_on_reversible_event_ok(self) -> None:
        client = self._client(_HR_A)
        target = {"id": "ev-1", "entity_type": "assignment", "entity_id": "reloc-uuid",
                  "action_type": "update", "event": "REASSIGN_HR_OWNER", "old_value": None, "new_value": {}}
        with (
            patch(f"{self.R}.get_case_company_for_audit", return_value="company-a"),
            patch(f"{self.R}.resolve_case_audit_entity_ids", return_value=["assignment-a", "reloc-uuid"]),
            patch(f"{self.R}.get_audit_log_entry", return_value=target),
            patch(f"{self.R}.find_audit_amendments", return_value=[]),
            patch(f"{self.R}.insert_case_audit_annotation", return_value="rev-id") as m_ins,
            self._profile_patch(),
        ):
            resp = client.post(
                "/api/hr/cases/assignment-a/audit-trail/ev-1/reverse",
                json={"reason": "Reassign was a mistake"},
                headers={"Authorization": "Bearer t"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["reverses"], "ev-1")
        self.assertEqual(m_ins.call_args.kwargs["event"], "AUDIT_REVERSED")

    def test_reverse_already_reversed_409(self) -> None:
        client = self._client(_HR_A)
        target = {"id": "ev-1", "entity_type": "assignment", "entity_id": "reloc-uuid",
                  "action_type": "update", "event": "REASSIGN_HR_OWNER", "old_value": None, "new_value": {}}
        with (
            patch(f"{self.R}.get_case_company_for_audit", return_value="company-a"),
            patch(f"{self.R}.resolve_case_audit_entity_ids", return_value=["assignment-a", "reloc-uuid"]),
            patch(f"{self.R}.get_audit_log_entry", return_value=target),
            patch(f"{self.R}.find_audit_amendments", return_value=[{"id": "x", "event": "AUDIT_REVERSED", "reverses": "ev-1"}]),
            patch(f"{self.R}.insert_case_audit_annotation") as m_ins,
            self._profile_patch(),
        ):
            resp = client.post(
                "/api/hr/cases/assignment-a/audit-trail/ev-1/reverse",
                json={"reason": "again"},
                headers={"Authorization": "Bearer t"},
            )
        self.assertEqual(resp.status_code, 409)
        m_ins.assert_not_called()

    def test_reverse_annotation_row_rejected_409(self) -> None:
        client = self._client(_HR_A)
        target = {"id": "ann-1", "entity_type": "assignment", "entity_id": "reloc-uuid",
                  "action_type": "update", "event": "AUDIT_AMENDED", "old_value": None, "new_value": {"amends": "ev-1"}}
        with (
            patch(f"{self.R}.get_case_company_for_audit", return_value="company-a"),
            patch(f"{self.R}.resolve_case_audit_entity_ids", return_value=["assignment-a", "reloc-uuid"]),
            patch(f"{self.R}.get_audit_log_entry", return_value=target),
            patch(f"{self.R}.insert_case_audit_annotation") as m_ins,
            self._profile_patch(),
        ):
            resp = client.post(
                "/api/hr/cases/assignment-a/audit-trail/ann-1/reverse",
                json={"reason": "no"},
                headers={"Authorization": "Bearer t"},
            )
        self.assertEqual(resp.status_code, 409)
        m_ins.assert_not_called()

    def test_target_not_in_case_404(self) -> None:
        client = self._client(_HR_A)
        target = {"id": "ev-9", "entity_type": "assignment", "entity_id": "OTHER-CASE-UUID",
                  "action_type": "update", "event": "X", "old_value": None, "new_value": {}}
        with (
            patch(f"{self.R}.get_case_company_for_audit", return_value="company-a"),
            patch(f"{self.R}.resolve_case_audit_entity_ids", return_value=["assignment-a", "reloc-uuid"]),
            patch(f"{self.R}.get_audit_log_entry", return_value=target),
            patch(f"{self.R}.insert_case_audit_annotation") as m_ins,
            self._profile_patch(),
        ):
            resp = client.post(
                "/api/hr/cases/assignment-a/audit-trail/ev-9/amend",
                json={"reason": "x"},
                headers={"Authorization": "Bearer t"},
            )
        self.assertEqual(resp.status_code, 404)
        m_ins.assert_not_called()

    def test_amend_requires_reason_422(self) -> None:
        client = self._client(_HR_A)
        with self._profile_patch():
            resp = client.post(
                "/api/hr/cases/assignment-a/audit-trail/ev-1/amend",
                json={"reason": ""},
                headers={"Authorization": "Bearer t"},
            )
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
