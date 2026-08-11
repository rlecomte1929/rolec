"""AIQ-1790 — GET /api/hr/cases/{case_id}/documents/{document_id}/fields.

The endpoint that finally shows a user WHAT the extraction engine read. Its sibling
GET /documents returns only aggregates (field_count, mean/min confidence), so before
this the pipeline could run, succeed, and the product would display none of it.

WHY A NEW FILE rather than extending test_hr_case_detail.py, which covers the sibling
endpoint: that module is in `collect_ignore` (backend/tests/conftest.py) and therefore
never runs in CI. Tests added there gate nothing — they pass by not executing, which is
the exact vacuous-pass trap this suite has been bitten by before. This file runs.

WHY dependency_overrides RATHER THAN patching db calls: test_hr_case_detail.py patches
`backend.app.auth_deps.db.get_profile_record` and reaches org_id through the real
dependency. That is what makes it order-dependent — standalone it 404s because the
dependency resolves differently. Overriding `get_org_id_for_hr_user` directly is
deterministic in any collection order.
"""
from __future__ import annotations

import unittest
from typing import Any, Dict, List, Optional

from fastapi.testclient import TestClient

from backend.main import app, UserRole

# The router depends on require_admin_or_hr → get_current_user from
# backend.app.auth_deps, NOT the same-named function in backend.main. Keying an
# override on the wrong one silently leaves the real auth path running (AIQ-567).
from backend.app.auth_deps import get_current_user, get_org_id_for_hr_user

_DOC_ID = "11111111-2222-3333-4444-555555555555"
_CASE_ID = "case-a"

_HR: Dict[str, Any] = {"id": "user-hr-a", "role": UserRole.HR.value,
                       "email": "hr-a@company-a.test", "is_admin": False}
_CASE: Dict[str, Any] = {"id": _CASE_ID, "company_id": "company-a",
                         "employee_id": "emp-a"}


def _field(key: str, value: Optional[str], conf: float = 1.0,
           page: Optional[int] = 1) -> Dict[str, Any]:
    return {"field_key": key, "value_raw": value, "confidence": conf,
            "resolution_status": "Resolved", "bbox_page": page}


def _engine(doc_row: Optional[Dict[str, Any]], field_rows: List[Dict[str, Any]]):
    """Engine double for the endpoint's two queries.

    Dispatches on the SQL text — the document lookup takes `.first()`, the field query
    `.all()`. Returns `field_rows` verbatim so the dedupe under test is the router's,
    never the fixture's.
    """
    class _Result:
        def __init__(self, rows):
            self._rows = rows

        def mappings(self):
            return self

        def first(self):
            return self._rows[0] if self._rows else None

        def all(self):
            return self._rows

    class _Conn:
        def execute(self, statement, params=None):
            return _Result(field_rows if "extracted_fields" in str(statement)
                           else ([doc_row] if doc_row else []))

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    class _Engine:
        def connect(self):
            return _Conn()

    return _Engine()


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        async def _user(request=None, authorization=None):  # type: ignore[override]
            return _HR

        async def _org():
            return "company-a"

        app.dependency_overrides[get_current_user] = _user
        app.dependency_overrides[get_org_id_for_hr_user] = _org
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _get(self, doc_row, field_rows, case=_CASE, doc_id=_DOC_ID, case_id=_CASE_ID):
        from unittest.mock import patch
        with (
            patch("backend.app.routers.hr_case_detail.db.get_relocation_case",
                  side_effect=lambda cid: case if (case and cid == case["id"]) else None),
            patch("backend.app.routers.hr_case_detail.db.engine",
                  new=_engine(doc_row, field_rows)),
        ):
            return self.client.get(
                f"/api/hr/cases/{case_id}/documents/{doc_id}/fields",
                headers={"Authorization": "Bearer t"},
            )


_DOC = {"document_id": _DOC_ID, "document_type_code": "PASSPORT_TD3"}


class TestDeduplication(_Base):
    """Re-processing a document APPENDS to extracted_fields rather than replacing.
    Production reads 22 rows for 13 real fields. Without dedupe every field renders
    twice and field_count lies to the user."""

    def test_a_twice_processed_document_reports_each_field_once(self) -> None:
        rows = [
            _field("document_number", "L898902C3"),   # newest
            _field("document_number", "L898902C0"),   # stale
            _field("surname", "ERIKSSON"),
            _field("surname", "ERIKSON"),
            _field("given_names", "ANNA MARIA"),
        ]
        resp = self._get(_DOC, rows)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["field_count"], 3, "5 rows must collapse to 3 fields")
        self.assertEqual([f["field_key"] for f in body["fields"]],
                         ["document_number", "surname", "given_names"])

    def test_the_newest_row_wins_not_the_stale_one(self) -> None:
        """Keeping the superseded value would show a stale reading at full confidence —
        worse than showing nothing. The SQL orders created_at DESC, so first-seen wins."""
        resp = self._get(_DOC, [_field("surname", "ERIKSSON"),
                                _field("surname", "STALE-WRONG")])
        self.assertEqual([f["value"] for f in resp.json()["fields"]], ["ERIKSSON"])

    def test_field_count_matches_the_returned_fields(self) -> None:
        resp = self._get(_DOC, [_field("a", "1"), _field("a", "2"), _field("b", "3")])
        body = resp.json()
        self.assertEqual(body["field_count"], len(body["fields"]))


class TestMasking(_Base):
    """Masked server-side so a client cannot leak an identifier by not knowing it is
    sensitive. NOT keyed off phi_class: all 22 production rows — passport number
    included — carry phi_class='NONE', so trusting that column would leak."""

    def test_identifying_numbers_never_reach_the_client(self) -> None:
        resp = self._get(_DOC, [_field("document_number", "L898902C3"),
                                _field("personal_number", "ZE184226B"),
                                _field("surname", "ERIKSSON")])
        blob = resp.text
        self.assertNotIn("L898902C3", blob, "the passport number reached the client")
        self.assertNotIn("ZE184226B", blob, "the personal number reached the client")

    def test_masked_fields_are_flagged_and_readable_ones_are_not(self) -> None:
        resp = self._get(_DOC, [_field("document_number", "L898902C3"),
                                _field("surname", "ERIKSSON")])
        by_key = {f["field_key"]: f for f in resp.json()["fields"]}
        self.assertTrue(by_key["document_number"]["masked"])
        # ...and non-identifying fields stay readable, or the panel is pointless.
        self.assertEqual(by_key["surname"]["value"], "ERIKSSON")
        self.assertFalse(by_key["surname"]["masked"])

    def test_a_masked_key_with_no_value_is_not_reported_as_masked(self) -> None:
        resp = self._get(_DOC, [_field("document_number", None)])
        field = resp.json()["fields"][0]
        self.assertIsNone(field["value"])
        self.assertFalse(field["masked"], "nothing was masked — there was no value")


class TestTenancyAndNotFound(_Base):
    def test_cross_tenant_returns_404_not_403(self) -> None:
        """404 by design so case ids cannot be enumerated by status code."""
        other = {**_CASE, "company_id": "company-b"}
        resp = self._get(_DOC, [_field("surname", "ERIKSSON")], case=other)
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn("ERIKSSON", resp.text)

    def test_a_missing_case_is_404(self) -> None:
        resp = self._get(_DOC, [], case=None)
        self.assertEqual(resp.status_code, 404)

    def test_a_document_belonging_to_another_case_is_404(self) -> None:
        """The caller proved access to THIS case, not to that document. The lookup keys
        on document_id AND case_id together, so a foreign document finds no row."""
        resp = self._get(None, [_field("surname", "ERIKSSON")])
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn("ERIKSSON", resp.text)

    def test_a_malformed_document_id_is_404_not_422(self) -> None:
        """A bad id must not read differently from another tenant's id."""
        resp = self._get(_DOC, [], doc_id="not-a-uuid")
        self.assertEqual(resp.status_code, 404)


class TestGracefulDegrade(_Base):
    def test_a_document_with_no_extracted_fields_is_empty_not_an_error(self) -> None:
        """The MAJORITY case today: only passports extract; every other type is gated on
        an unset MISTRAL_API_KEY. Must read as 'not yet processed', never as broken."""
        resp = self._get({"document_id": _DOC_ID, "document_type_code": "MARRIAGE_CERT"}, [])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["field_count"], 0)
        self.assertEqual(resp.json()["fields"], [])

    def test_an_unavailable_rce_schema_degrades_instead_of_500(self) -> None:
        from unittest.mock import patch

        class _Failing:
            def connect(self):
                raise RuntimeError("simulated: rce schema absent")

        with (
            patch("backend.app.routers.hr_case_detail.db.get_relocation_case",
                  side_effect=lambda cid: _CASE if cid == _CASE_ID else None),
            patch("backend.app.routers.hr_case_detail.db.engine", new=_Failing()),
        ):
            resp = self.client.get(
                f"/api/hr/cases/{_CASE_ID}/documents/{_DOC_ID}/fields",
                headers={"Authorization": "Bearer t"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["fields"], [])


class TestRouteIsReachableInProduction(unittest.TestCase):
    def test_registered_on_the_app_render_actually_boots(self) -> None:
        """Render boots `uvicorn backend.main:app`. A route registered only on the
        modular app 405s in production — the AI-002 incident. hr_case_detail is
        registered in BOTH entry points, so this asserts the inheritance holds."""
        paths = {getattr(r, "path", "") for r in app.routes}
        self.assertIn("/api/hr/cases/{case_id}/documents/{document_id}/fields", paths)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
