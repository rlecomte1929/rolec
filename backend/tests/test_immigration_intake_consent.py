"""
AIQ-832 / F1 · Tests for fail-closed behaviour on the live immigration-requirements
endpoint (GET /api/hr/cases/{case_id}/immigration-requirements), served by
backend.app.routers.immigration_intake_consent.

Guards the correctness fix: a case with missing geography or an unseeded corridor
must return HTTP 200 with covered=False — never the old silent FR→DE default
checklist. A valid seeded corridor must still return covered=True with its real
requirements.
"""
from __future__ import annotations

import os

# App-mounted harness: disable the per-request query counter and rate limits
# before importing backend.main (mirrors tests/conftest.py).
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app, UserRole

# The endpoint depends on require_admin_or_hr + get_org_id_for_hr_user from
# backend.app.auth_deps. Override those references directly so the test bypasses
# the real DB-backed auth/company resolution.
from backend.app.auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from backend.app.services.immigration_requirement_service import RequirementResult

_HR_USER: Dict[str, Any] = {
    "id": "user-hr-a",
    "role": UserRole.HR.value,
    "email": "hr-a@company-a.test",
    "is_admin": False,
}

_CONSENT_MOD = "backend.app.routers.immigration_intake_consent"


def _make_requirement(document_name: str = "Passport") -> RequirementResult:
    """A minimal but complete RequirementResult for the covered-corridor case."""
    return RequirementResult(
        document_type="passport",
        document_name=document_name,
        is_required=True,
        is_conditional=False,
        freshness_days=None,
        requires_apostille=False,
        apostille_countries=[],
        requires_translation=False,
        translation_languages=[],
        can_be_prefilled=False,
        can_be_ocr_extracted=False,
        typical_processing_days=21,
        book_early_flag=False,
        book_early_reason=None,
        success_tips=[],
        common_rejection_reasons=[],
        form_url=None,
        form_version=None,
    )


class _BaseEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[require_admin_or_hr] = lambda: _HR_USER
        app.dependency_overrides[get_org_id_for_hr_user] = lambda: "company-a"
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _get(
        self,
        case: Optional[Dict[str, Any]],
        requirements: List[RequirementResult],
    ):
        """Call the endpoint with patched case lookup + requirements service."""
        with patch(f"{_CONSENT_MOD}._get_case_details", return_value=case), \
                patch(f"{_CONSENT_MOD}.get_requirements", return_value=requirements), \
                patch(f"{_CONSENT_MOD}._load_profile_for_case", return_value=None), \
                patch(f"{_CONSENT_MOD}._log_access", return_value=None):
            return self.client.get("/api/hr/cases/case-a/immigration-requirements")


class TestFailClosed(_BaseEndpointTest):
    def test_missing_origin_country_fails_closed(self) -> None:
        """(a) origin_country=null → covered=False, not Blue Card requirements."""
        case = {"origin_country": None, "dest_country": "DE"}
        resp = self._get(case, requirements=[_make_requirement()])
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["covered"])
        self.assertEqual(body["coverage_reason"], "corridor_not_supported")
        self.assertEqual(body["requirements"], [])
        self.assertEqual(body["document_count"], 0)
        self.assertIsNone(body["estimated_timeline_days"])

    def test_missing_dest_country_fails_closed(self) -> None:
        """(b) dest_country=null → covered=False."""
        case = {"origin_country": "NO", "dest_country": None}
        resp = self._get(case, requirements=[_make_requirement()])
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["covered"])
        self.assertEqual(body["coverage_reason"], "corridor_not_supported")
        self.assertIsNone(body["estimated_timeline_days"])

    def test_unseeded_corridor_fails_closed_with_corridor_string(self) -> None:
        """(c) valid but unseeded corridor NO→JP → covered=False, corridor 'NO→JP'."""
        case = {"origin_country": "NO", "dest_country": "JP"}
        resp = self._get(case, requirements=[])  # empty = corridor not seeded
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["covered"])
        self.assertEqual(body["coverage_reason"], "corridor_not_supported")
        self.assertEqual(body["corridor"], "NO→JP")
        self.assertEqual(body["requirements"], [])
        self.assertEqual(body["document_count"], 0)
        self.assertIsNone(body["estimated_timeline_days"])

    def test_uncovered_path_still_writes_audit_log(self) -> None:
        """Fail-closed must still record the HR view in the access audit trail
        (parity with the covered path; regression guard for the early returns)."""
        case = {"origin_country": "NO", "dest_country": "JP"}
        with patch(f"{_CONSENT_MOD}._get_case_details", return_value=case), \
                patch(f"{_CONSENT_MOD}.get_requirements", return_value=[]), \
                patch(f"{_CONSENT_MOD}._load_profile_for_case", return_value=None), \
                patch(f"{_CONSENT_MOD}._log_access") as mock_log:
            resp = self.client.get("/api/hr/cases/case-a/immigration-requirements")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["covered"])
        mock_log.assert_called_once()
        self.assertEqual(mock_log.call_args.kwargs.get("action"), "view")


class TestCovered(_BaseEndpointTest):
    def test_seeded_corridor_returns_covered_true(self) -> None:
        """(d) valid seeded corridor FR→DE → covered=True with real requirements."""
        case = {"origin_country": "FR", "dest_country": "DE"}
        resp = self._get(case, requirements=[_make_requirement("Passport")])
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["covered"])
        self.assertIsNone(body["coverage_reason"])
        self.assertEqual(body["corridor"], "FR→DE")
        self.assertEqual(body["document_count"], 1)
        self.assertGreater(len(body["requirements"]), 0)
        self.assertIsNotNone(body["estimated_timeline_days"])

    def test_explicit_query_corridor_does_not_hit_case_lookup(self) -> None:
        """corridor passed explicitly → covered=True without deriving from case."""
        with patch(f"{_CONSENT_MOD}.get_requirements", return_value=[_make_requirement()]), \
                patch(f"{_CONSENT_MOD}._load_profile_for_case", return_value=None), \
                patch(f"{_CONSENT_MOD}._log_access", return_value=None):
            resp = self.client.get(
                "/api/hr/cases/case-a/immigration-requirements"
                "?corridor_from=FR&corridor_to=DE"
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["covered"])
        self.assertEqual(body["corridor"], "FR→DE")


if __name__ == "__main__":
    unittest.main()
