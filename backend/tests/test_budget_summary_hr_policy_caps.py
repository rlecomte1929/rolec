"""AIQ-1551 — the FULL HR-policy CAP list surfaces on the estimate API.

The estimate page already showed caps per *selected* service (BudgetSummaryTable). This
adds `hr_policy_caps` to GET /api/cases/{id}/budget-summary: the complete list of the
company's published CAPs, so the page can show everything HR configured even when no
matching service is selected (the reported bug: BUG-260715-557D). Caps are resolved ONCE
(reused for the per-service rows) and honestly shaped (no fabricated amounts).
"""
import contextlib
import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

import backend.app.routers.cases_read as cr  # noqa: E402
from backend.app.services import policy_config_matrix_service as mxs  # noqa: E402
from backend.app import auth_deps  # noqa: E402
from backend.main import app  # noqa: E402


def _cap(benefit_key, label, amount=None, currency=None,
         cap_type="currency_amount", category="compensation_allowances"):
    return {
        "benefit_key": benefit_key, "benefit_label": label, "category": category,
        "covered": True, "normalized_cap_type": cap_type, "normalized_amount": amount,
        "currency_code": currency, "unit_frequency": "yearly", "notes": None,
    }


def test_shape_hr_policy_caps_maps_and_is_honest():
    out = cr._shape_hr_policy_caps([
        _cap("host_housing_cap", "Housing allowance", 2000.0, "EUR"),
        _cap("settling_in_services", "Settling-in", None, None, cap_type="no_monetary_cap"),
    ])
    assert isinstance(out, list) and len(out) == 2
    assert out[0] == {
        "benefit_key": "host_housing_cap", "name": "Housing allowance",
        "category": "compensation_allowances", "cap_type": "currency_amount",
        "amount": 2000.0, "currency": "EUR", "unit_frequency": "yearly", "notes": None,
    }
    # Honest: a covered-but-unquantified benefit keeps amount null — never a fabricated number.
    assert out[1]["amount"] is None and out[1]["name"] == "Settling-in"
    assert cr._shape_hr_policy_caps([]) == []


def test_published_caps_bundle_scopes_and_degrades(monkeypatch):
    # No company → empty, and the service is never called.
    assert cr._published_caps_bundle("", None, None) == {"caps": []}
    monkeypatch.setattr(
        mxs.PolicyConfigMatrixService, "caps_payload",
        lambda self, cid, **kw: {"metadata": {"company_id": cid}, "caps": [_cap("x", "X", 1.0, "EUR")]},
    )
    assert cr._published_caps_bundle("co-1", None, None)["caps"][0]["benefit_key"] == "x"


def test_estimate_endpoint_returns_full_hr_policy_caps(monkeypatch):
    caps = [
        _cap("host_housing_cap", "Housing allowance", 2000.0, "EUR"),
        _cap("visa_work_permit_assistance", "Visa support", 1500.0, "EUR"),
    ]
    monkeypatch.setattr(mxs.PolicyConfigMatrixService, "caps_payload",
                        lambda self, cid, **kw: {"metadata": {"has_published_config": True}, "caps": caps})
    monkeypatch.setattr(cr, "_assert_case_access", lambda *a, **k: None)
    monkeypatch.setattr(cr.main_db, "get_assignment_by_case_id",
                        lambda cid: {"id": "a1", "assignment_type": None, "family_status": None})
    monkeypatch.setattr(cr.main_db, "get_company_id_for_assignment_id", lambda aid: "co-1")
    monkeypatch.setattr(cr, "_case_service_estimates", lambda cid: {})
    monkeypatch.setattr(cr, "SessionLocal", lambda: contextlib.nullcontext(None))
    monkeypatch.setattr(cr.crud, "get_case", lambda sess, cid: None)  # NO services selected

    app.dependency_overrides[auth_deps.get_current_user] = lambda: {"id": "emp-1", "role": "EMPLOYEE", "company": "co-1"}
    try:
        resp = TestClient(app).get("/api/cases/case-x/budget-summary")
    finally:
        app.dependency_overrides.pop(auth_deps.get_current_user, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body.get("hr_policy_caps"), list)
    # The FULL published list is present even though no service was selected (the reported gap).
    assert {c["name"] for c in body["hr_policy_caps"]} == {"Housing allowance", "Visa support"}
    assert "categories" in body  # existing data still returned (no regression)


def test_injected_caps_avoid_a_second_fetch(monkeypatch):
    """When get_budget_summary passes caps_by_key, the per-service helper must NOT re-query
    (the no-N+1 constraint)."""
    calls = {"n": 0}

    def _counting(self, cid, **kw):
        calls["n"] += 1
        return {"caps": []}

    monkeypatch.setattr(mxs.PolicyConfigMatrixService, "caps_payload", _counting)
    caps_by_key = {"host_housing_cap": {
        "benefit_key": "host_housing_cap", "normalized_cap_type": "currency_amount",
        "normalized_amount": 2000.0, "currency_code": "EUR",
    }}
    rows = cr._budget_categories_from_policy_config("co-1", ["housing"], None, None, caps_by_key=caps_by_key)
    assert rows[0]["cap_amount"] == 2000.0
    assert calls["n"] == 0  # reused the injected map — no re-fetch


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
