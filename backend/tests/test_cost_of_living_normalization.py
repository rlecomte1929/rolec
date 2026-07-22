"""Cost-of-living: the housing cost-vs-cap comparison must be FX-normalized.

The company housing cap is in the policy currency; the estimated cost is in USD.
The old policy-fit compared them raw (an NOK/USD figure vs a EUR cap). Now the cost
is converted into the policy currency before comparing, and a % of the cap is
surfaced for the card.
"""
from __future__ import annotations

from backend.app.recommendations.explanation import _derive_policy_fit


def _meta(usd):
    return {"estimated_cost_usd": usd, "estimated_cost_local": usd, "currency": "USD"}


def test_within_cap_after_fx_normalization():
    # cap 3000 EUR; cost 2000 USD → ~1835 EUR → within.
    fit, flags, pct = _derive_policy_fit(
        _meta(2000), {"_policy_cap_monthly": 3000, "_policy_currency": "EUR"}, "living_areas")
    assert fit == "within"
    assert "above_policy" not in flags
    assert pct is not None and pct < 100


def test_above_cap_flags_and_pct_over_100():
    # cap 1000 EUR; cost 2000 USD → ~1835 EUR → above.
    fit, flags, pct = _derive_policy_fit(
        _meta(2000), {"_policy_cap_monthly": 1000, "_policy_currency": "EUR"}, "living_areas")
    assert fit == "above_policy"
    assert "above_policy" in flags
    assert pct is not None and pct > 100


def test_no_cap_is_unknown_with_no_pct():
    fit, flags, pct = _derive_policy_fit(_meta(2000), {"_policy_currency": "EUR"}, "living_areas")
    assert fit == "unknown"
    assert pct is None


def test_pct_reflects_fx_conversion_not_raw_ratio():
    # cost 1000 USD, cap 1000 EUR. Raw ratio would be exactly 100%; after converting the
    # cost into EUR (rate < 1) it is < 100% — proving the comparison is FX-normalized,
    # rate-agnostic beyond "EUR is worth more than USD".
    _fit, _flags, pct = _derive_policy_fit(
        _meta(1000), {"_policy_cap_monthly": 1000, "_policy_currency": "EUR"}, "living_areas")
    assert pct is not None and pct != 100.0
