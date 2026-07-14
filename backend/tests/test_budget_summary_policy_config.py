"""Budget-summary now sources caps from the canonical policy_config matrix
(caps_payload) instead of the dead legacy hr_policies table.

These tests pin the intake-service → benefit-key rollup in
`_budget_categories_from_policy_config` without touching the DB: the matrix
service's `caps_payload` is patched to return a canonical caps bundle.
"""
import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import backend.app.routers.cases_read as cr  # noqa: E402
from backend.app.services import policy_config_matrix_service as mxs  # noqa: E402


def _bundle(caps):
    return {"metadata": {"has_published_config": True}, "caps": caps}


def _currency_cap(benefit_key, amount, currency="EUR"):
    return {
        "benefit_key": benefit_key,
        "normalized_cap_type": "currency_amount",
        "normalized_amount": amount,
        "currency_code": currency,
    }


def test_maps_published_caps_to_selected_services(monkeypatch):
    caps = [
        _currency_cap("host_housing_cap", 2000.0),
        _currency_cap("visa_work_permit_assistance", 1500.0),
    ]
    monkeypatch.setattr(
        mxs.PolicyConfigMatrixService, "caps_payload",
        lambda self, company_id, **kw: _bundle(caps),
    )

    rows = cr._budget_categories_from_policy_config(
        "co-1", ["housing", "immigration", "banking"], None, None
    )
    by_name = {r["name"]: r for r in rows}

    assert by_name["housing"]["cap_amount"] == 2000.0
    assert by_name["immigration"]["cap_amount"] == 1500.0

    # [AIQ-1527] These used to assert "within_budget" — with NO estimate passed in. The test was
    # locking in the defect: a green tick derived from nothing. A cap on its own tells you what
    # you MAY spend, never what you WILL. With no estimate the honest answer is "no_estimate".
    assert by_name["housing"]["status"] == "no_estimate"
    assert by_name["immigration"]["status"] == "no_estimate"
    assert by_name["housing"]["estimated_amount"] is None

    # An intake service with no mapped benefit key stays uncapped.
    assert by_name["banking"]["cap_amount"] is None
    assert by_name["banking"]["status"] == "no_cap"


def test_a_real_estimate_is_actually_compared_against_the_cap(monkeypatch):
    """[AIQ-1527] The comparison the endpoint always claimed to be making, and never was."""
    monkeypatch.setattr(
        mxs.PolicyConfigMatrixService, "caps_payload",
        lambda self, company_id, **kw: _bundle([_currency_cap("host_housing_cap", 2000.0)]),
    )
    under = cr._budget_categories_from_policy_config(
        "co-1", ["housing"], None, None, estimates={"housing": {"amount": 1800.0, "currency": "EUR"}},
    )
    assert under[0]["status"] == "within_budget"
    assert under[0]["estimated_amount"] == 1800.0

    over = cr._budget_categories_from_policy_config(
        "co-1", ["housing"], None, None, estimates={"housing": {"amount": 2400.0, "currency": "EUR"}},
    )
    assert over[0]["status"] == "over_budget"

    # A currency mismatch refuses to rank rather than inventing an FX rate.
    mismatched = cr._budget_categories_from_policy_config(
        "co-1", ["housing"], None, None, estimates={"housing": {"amount": 1800.0, "currency": "USD"}},
    )
    assert mismatched[0]["status"] == "not_comparable"


def test_sums_multiple_benefit_keys_for_one_service(monkeypatch):
    # `moving` rolls up shipment + removal + storage.
    caps = [
        _currency_cap("shipment_of_goods", 3000.0),
        _currency_cap("removal_expenses", 1000.0),
        _currency_cap("storage", 500.0),
    ]
    monkeypatch.setattr(
        mxs.PolicyConfigMatrixService, "caps_payload",
        lambda self, company_id, **kw: _bundle(caps),
    )

    rows = cr._budget_categories_from_policy_config("co-1", ["moving"], None, None)
    assert rows[0]["name"] == "moving"
    assert rows[0]["cap_amount"] == 4500.0
    # [AIQ-1527] The cap sums correctly — but no estimate was supplied, so there is nothing to
    # compare it to. Was "within_budget"; that was the bug.
    assert rows[0]["status"] == "no_estimate"


def test_no_company_yields_all_no_cap(monkeypatch):
    # No company → never calls the service; every selected service is no_cap.
    def _boom(*a, **k):
        raise AssertionError("caps_payload must not be called without a company")

    monkeypatch.setattr(mxs.PolicyConfigMatrixService, "caps_payload", _boom)
    rows = cr._budget_categories_from_policy_config("", ["housing", "moving"], None, None)
    assert [r["status"] for r in rows] == ["no_cap", "no_cap"]
    assert all(r["cap_amount"] is None for r in rows)


def test_non_currency_caps_are_not_counted(monkeypatch):
    # A percentage / qualitative cap is not a spendable allowance → no_cap.
    caps = [{
        "benefit_key": "host_housing_cap",
        "normalized_cap_type": "percentage",
        "normalized_amount": 80.0,
        "currency_code": None,
    }]
    monkeypatch.setattr(
        mxs.PolicyConfigMatrixService, "caps_payload",
        lambda self, company_id, **kw: _bundle(caps),
    )
    rows = cr._budget_categories_from_policy_config("co-1", ["housing"], None, None)
    assert rows[0]["status"] == "no_cap"
    assert rows[0]["cap_amount"] is None
