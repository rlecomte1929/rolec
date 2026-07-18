"""[AIQ-1611 / F14] The over-cap → Policy Exception path must be able to fire.

Before this fix the budget-summary join keyed on the intake vocabulary (`moving`)
and omitted banks/electricity/insurances/pets, so every catalog service fell
through to `no_cap` and `over_budget` could never happen. These tests pin the
corrected service→benefit_key bridge and the honest status logic.
"""
import os
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.app.routers.cases_read import _budget_categories_from_policy_config
from backend.app.services.policy_config_cap_compare import NORMALIZED_CURRENCY_AMOUNT


def _cap(amount, currency="EUR"):
    return {
        "normalized_cap_type": NORMALIZED_CURRENCY_AMOUNT,
        "normalized_amount": amount,
        "currency_code": currency,
    }


def _rows(services, caps, estimates=None):
    return {
        r["name"]: r
        for r in _budget_categories_from_policy_config(
            company_id="co-1",
            selected_services=services,
            assignment_type=None,
            family_status=None,
            estimates=estimates or {},
            caps_by_key=caps,
        )
    }


def test_housing_over_cap_fires():
    rows = _rows(
        ["housing"],
        {"host_housing_cap": _cap(1000)},
        {"housing": {"amount": 1500, "currency": "EUR"}},
    )
    assert rows["housing"]["status"] == "over_budget"
    assert rows["housing"]["cap_amount"] == 1000


def test_movers_sums_its_three_benefit_keys():
    # movers → shipment_of_goods + removal_expenses + storage
    rows = _rows(
        ["movers"],
        {
            "shipment_of_goods": _cap(500),
            "removal_expenses": _cap(300),
            "storage": _cap(200),
        },
        {"movers": {"amount": 900, "currency": "EUR"}},
    )
    assert rows["movers"]["cap_amount"] == 1000
    assert rows["movers"]["status"] == "within_budget"


def test_banks_now_maps_to_a_cap():
    # Regression guard: `banks` used to be absent from the map → always no_cap.
    rows = _rows(
        ["banks"],
        {"banking_assistance": _cap(800)},
        {"banks": {"amount": 950, "currency": "EUR"}},
    )
    assert rows["banks"]["status"] == "over_budget"


def test_uncapped_service_is_honest_no_cap():
    # pets has no config-matrix benefit → no_cap, never a false within_budget.
    rows = _rows(["pets"], {"host_housing_cap": _cap(1000)}, {"pets": {"amount": 50, "currency": "EUR"}})
    assert rows["pets"]["status"] == "no_cap"
    assert rows["pets"]["cap_amount"] is None
