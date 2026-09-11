"""
H4 · API-level tests for immigration HTTP endpoints with no existing app-mounted
coverage (the campaign API runner has no Immigration coverage):

  GET /api/hr/cases/{case_id}/immigration/available-forms   (immigration_forms.py)
  GET /api/employee/cases/{case_id}/interview/status         (immigration_status.py)

Both are exercised through the prod app (backend.main) with their service/DB layer
patched, so no live DB is needed. Mirrors the override pattern in
test_immigration_intake_consent.py.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import unittest
from typing import Any, Dict
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app, UserRole
from backend.app.auth_deps import (
    get_current_user,
    get_org_id_for_hr_user,
    require_admin_or_hr,
    require_hr_or_employee,
)
from fastapi import HTTPException

_HR_USER: Dict[str, Any] = {
    "id": "user-hr-a", "role": UserRole.HR.value,
    "email": "hr-a@company-a.test", "is_admin": False,
}
_EMP_USER: Dict[str, Any] = {
    "id": "user-emp", "role": "EMPLOYEE", "auth_uuid": "11111111-1111-1111-1111-111111111111",
    "org_id": "company-a", "email": "emp@company-a.test",
}

_FORMS_MOD = "backend.app.routers.immigration_forms"
_STATUS_MOD = "backend.app.routers.immigration_status"


class _Form:
    """Minimal stand-in for a form descriptor with a to_dict()."""
    def __init__(self, form_id: str, name: str) -> None:
        self._d = {"form_id": form_id, "name": name}

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._d)


class AvailableFormsTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[require_admin_or_hr] = lambda: _HR_USER
        app.dependency_overrides[get_org_id_for_hr_user] = lambda: "company-a"
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_explicit_corridor_skips_case_lookup(self) -> None:
        """corridor_to passed explicitly → forms returned without a case lookup."""
        with patch(f"{_FORMS_MOD}.get_available_forms",
                   return_value=[_Form("blue_card_fill", "Blue Card")]) as mock_forms, \
                patch(f"{_FORMS_MOD}._get_case_details") as mock_case:
            resp = self.client.get(
                "/api/hr/cases/case-a/immigration/available-forms",
                params={"corridor_to": "DE", "visa_type": "blue_card"},
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["corridor_to"], "DE")
        self.assertEqual(body["visa_type"], "blue_card")
        self.assertEqual(body["forms"], [{"form_id": "blue_card_fill", "name": "Blue Card"}])
        mock_case.assert_not_called()
        mock_forms.assert_called_once_with("DE", "blue_card")

    def test_corridor_derived_from_case_when_omitted(self) -> None:
        """No corridor_to → derive dest_country from the case details.

        [AIQ-1771] Updated: NO has no mapped forms, so the router now short-circuits
        to an empty list WITHOUT calling get_available_forms. Previously it queried
        NO+blue_card — a combination that cannot exist — and got an empty result by
        accident rather than by design. Norway is a portal/data-sheet corridor
        (FINDINGS.md Appendix A.1); no fillable form is the correct answer.
        """
        with patch(f"{_FORMS_MOD}.get_available_forms", return_value=[]) as mock_forms, \
                patch(f"{_FORMS_MOD}.visa_types_for_corridor", return_value=[]), \
                patch(f"{_FORMS_MOD}._get_case_details",
                      return_value={"dest_country": "NO"}) as mock_case:
            resp = self.client.get("/api/hr/cases/case-a/immigration/available-forms")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["corridor_to"], "NO")
        self.assertEqual(resp.json()["forms"], [])
        mock_case.assert_called_once()
        mock_forms.assert_not_called()

    def test_missing_case_422s_instead_of_defaulting_to_DE(self) -> None:
        """[AIQ-1771] REPLACES test_corridor_falls_back_to_DE_when_case_missing.

        That test asserted `corridor_to == "DE"` and called it a "safe DE default".
        It was not safe: a case with no resolvable destination was offered the
        GERMAN Blue Card form, presented as the right one. Silently answering a
        question you cannot answer is the defect, so the contract is now fail-closed.
        """
        with patch(f"{_FORMS_MOD}.get_available_forms", return_value=[]) as mock_forms, \
                patch(f"{_FORMS_MOD}._get_case_details", return_value=None):
            resp = self.client.get("/api/hr/cases/case-a/immigration/available-forms")
        self.assertEqual(resp.status_code, 422)
        self.assertIn("destination corridor", resp.json()["detail"])
        mock_forms.assert_not_called()


class EmployeeInterviewStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: _EMP_USER
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_consent_required_returns_403(self) -> None:
        with patch(f"{_STATUS_MOD}._check_consent", return_value=False):
            resp = self.client.get("/api/employee/cases/case-a/interview/status")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Consent", resp.json()["detail"])

    def test_no_session_returns_empty_progress(self) -> None:
        with patch(f"{_STATUS_MOD}._check_consent", return_value=True), \
                patch(f"{_STATUS_MOD}._load_session", return_value=None):
            resp = self.client.get("/api/employee/cases/case-a/interview/status")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["has_session"])
        self.assertEqual(body["completion_pct"], 0)
        self.assertFalse(body["is_complete"])


class _PrefillResult:
    """Stand-in for PrefilledPdfResult with the two fields the route reads."""
    download_url = "https://signed.example/prefilled.pdf"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filled_count": 2, "blank_count": 1, "warning_count": 0,
            "not_in_pdf_count": 0, "fields": [],
        }


class EmployeeFormPrefillTest(unittest.TestCase):
    """[AIQ-1855] The employee-facing pre-fill routes. The load-bearing test is
    cross-case access: a caller may only reach a case their assignment owns."""

    def setUp(self) -> None:
        app.dependency_overrides[require_hr_or_employee] = lambda: _EMP_USER
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_available_forms_own_case_returns_forms(self) -> None:
        with patch(f"{_FORMS_MOD}.require_case_access", return_value={}), \
                patch(f"{_FORMS_MOD}.get_available_forms",
                      return_value=[_Form("blue_card_fill", "Blue Card")]) as mock_forms:
            resp = self.client.get(
                "/api/employee/cases/case-a/immigration/available-forms",
                params={"corridor_to": "DE", "visa_type": "blue_card"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["forms"], [{"form_id": "blue_card_fill", "name": "Blue Card"}])
        mock_forms.assert_called_once_with("DE", "blue_card")

    def test_available_forms_cross_case_is_forbidden(self) -> None:
        # require_case_access raises for a case the caller does not own → the route
        # must surface that BEFORE resolving or returning any form.
        with patch(f"{_FORMS_MOD}.require_case_access",
                   side_effect=HTTPException(status_code=403, detail="Not authorised for this case")), \
                patch(f"{_FORMS_MOD}.get_available_forms") as mock_forms:
            resp = self.client.get(
                "/api/employee/cases/someone-elses-case/immigration/available-forms",
                params={"corridor_to": "DE", "visa_type": "blue_card"},
            )
        self.assertEqual(resp.status_code, 403)
        mock_forms.assert_not_called()

    def test_available_forms_resolves_corridor_from_case_when_omitted(self) -> None:
        # No corridor_to passed → resolved from the case (ownership already checked).
        with patch(f"{_FORMS_MOD}.require_case_access", return_value={}), \
                patch(f"{_FORMS_MOD}._get_case_details",
                      return_value={"dest_country": "DE"}) as mock_case, \
                patch(f"{_FORMS_MOD}.visa_types_for_corridor", return_value=["blue_card"]), \
                patch(f"{_FORMS_MOD}.get_available_forms",
                      return_value=[_Form("blue_card_fill", "Blue Card")]):
            resp = self.client.get("/api/employee/cases/case-a/immigration/available-forms")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["corridor_to"], "DE")
        mock_case.assert_called_once()

    def test_generate_cross_case_is_forbidden_before_vault_read(self) -> None:
        with patch(f"{_FORMS_MOD}.require_case_access",
                   side_effect=HTTPException(status_code=403, detail="Not authorised for this case")), \
                patch(f"{_FORMS_MOD}._load_profile_for_case_employee") as mock_profile, \
                patch(f"{_FORMS_MOD}.generate_prefilled_pdf") as mock_gen:
            resp = self.client.post(
                "/api/employee/cases/someone-elses-case/immigration/generate-form",
                json={"form_id": "blue_card_fill"},
            )
        self.assertEqual(resp.status_code, 403)
        mock_profile.assert_not_called()  # no vault read on a case we don't own
        mock_gen.assert_not_called()

    def test_generate_requires_consent(self) -> None:
        with patch(f"{_FORMS_MOD}.require_case_access", return_value={}), \
                patch(f"{_FORMS_MOD}._check_consent", return_value=False), \
                patch(f"{_FORMS_MOD}._load_profile_for_case_employee") as mock_profile:
            resp = self.client.post(
                "/api/employee/cases/case-a/immigration/generate-form",
                json={"form_id": "blue_card_fill"},
            )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("consent", resp.json()["detail"].lower())
        mock_profile.assert_not_called()  # consent gate is before the vault read

    def test_generate_missing_profile_returns_404(self) -> None:
        with patch(f"{_FORMS_MOD}.require_case_access", return_value={}), \
                patch(f"{_FORMS_MOD}._check_consent", return_value=True), \
                patch(f"{_FORMS_MOD}._load_profile_for_case_employee", return_value=None):
            resp = self.client.post(
                "/api/employee/cases/case-a/immigration/generate-form",
                json={"form_id": "blue_card_fill"},
            )
        self.assertEqual(resp.status_code, 404)

    def test_generate_own_case_returns_download_and_report(self) -> None:
        with patch(f"{_FORMS_MOD}.require_case_access", return_value={}), \
                patch(f"{_FORMS_MOD}._check_consent", return_value=True), \
                patch(f"{_FORMS_MOD}._load_profile_for_case_employee",
                      return_value={"id": "prof-1"}) as mock_profile, \
                patch(f"{_FORMS_MOD}._decrypt_passport", side_effect=lambda p: p), \
                patch(f"{_FORMS_MOD}.generate_prefilled_pdf", return_value=_PrefillResult()), \
                patch(f"{_FORMS_MOD}._log_access"):
            resp = self.client.post(
                "/api/employee/cases/case-a/immigration/generate-form",
                json={"form_id": "FR_cerfa_14571_v2024"},
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["download_url"], "https://signed.example/prefilled.pdf")
        self.assertEqual(body["fill_report"]["filled_count"], 2)
        # The vault is loaded scoped to the CALLER's own id, never the path.
        mock_profile.assert_called_once_with("case-a", "user-emp")

    def test_generate_rejects_a_non_fillable_form(self) -> None:
        # Defense in depth: even past ownership + consent + profile, a direct POST naming a
        # synthetic/non-fillable form (DE_blue_card_v2024 has no real PDF) must 404 without
        # decrypting the passport or generating anything.
        with patch(f"{_FORMS_MOD}.require_case_access", return_value={}), \
                patch(f"{_FORMS_MOD}._check_consent", return_value=True), \
                patch(f"{_FORMS_MOD}._load_profile_for_case_employee",
                      return_value={"id": "prof-1"}), \
                patch(f"{_FORMS_MOD}._decrypt_passport") as mock_decrypt, \
                patch(f"{_FORMS_MOD}.generate_prefilled_pdf") as mock_gen:
            resp = self.client.post(
                "/api/employee/cases/case-a/immigration/generate-form",
                json={"form_id": "DE_blue_card_v2024"},
            )
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not available", resp.json()["detail"].lower())
        mock_gen.assert_not_called()      # never reached the fill for a synthetic form
        mock_decrypt.assert_not_called()  # and never decrypted the passport for it


if __name__ == "__main__":
    unittest.main()
