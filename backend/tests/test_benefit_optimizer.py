"""Tests for the Markowitz-style benefit-mix optimizer (Parker-B).

Skipped cleanly when PuLP is not installed, so the rest of the suite stays green
on machines without the solver. Install with `pip install -r backend/requirements.txt`.
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("pulp")

from backend.app.services.benefit_optimizer import (  # noqa: E402
    BenefitCandidate,
    OptimizationError,
    default_variance,
    optimize,
)


# ── Happy path: hand-solved 3-benefit toy ─────────────────────────────────────
#
# costs/sat/var and λ=0.1 give utilities a=9.6, b=11.1, c=7.9.
# Within budget 8000 the best feasible mix is {a,b}: utility 20.7, cost 7000
# ({a,c}=17.5@8000, {b,c}=19.0 but costs 9000 > budget).
def _toy_three():
    return [
        BenefitCandidate("a", "housing", 3000, 10, variance=4),
        BenefitCandidate("b", "transport", 4000, 12, variance=9),
        BenefitCandidate("c", "education", 5000, 8, variance=1),
    ]


def test_hand_solved_three_benefit_optimum():
    result = optimize(budget=8000, candidates=_toy_three(), lambda_risk=0.1)
    assert result.feasible
    assert result.selected == ["a", "b"]
    assert result.achieved_utility == pytest.approx(20.7)
    assert result.total_cost == pytest.approx(7000.0)


def test_default_variance_prior():
    assert default_variance(4) == pytest.approx(0.25 * 16)
    # A candidate with no explicit variance uses the prior in its utility.
    c = BenefitCandidate("x", "cat", 1000, 10)
    assert c.effective_variance() == pytest.approx(25.0)  # 0.25 * 100


# ── Edge: mandatory set exceeds budget → structured infeasibility ─────────────


def test_mandatory_exceeds_budget():
    result = optimize(
        budget=1000,
        candidates=_toy_three(),
        mandatory_ids=["a", "b", "c"],
        lambda_risk=0.1,
    )
    assert result.feasible is False
    assert result.infeasibility_reason == "mandatory_exceeds_budget"
    assert result.selected == []


# ── Failure mode: category cap binds → second-best in that category ───────────


def test_category_cap_forces_second_best():
    # Both in "housing": d is better (util 20) but costs 5000; cap 4000 forbids it,
    # so the solver must fall back to e (util 12, cost 3000).
    candidates = [
        BenefitCandidate("d", "housing", 5000, 20, variance=0),
        BenefitCandidate("e", "housing", 3000, 12, variance=0),
    ]
    result = optimize(
        budget=10000,
        candidates=candidates,
        category_caps={"housing": 4000},
        lambda_risk=0.0,
    )
    assert result.feasible
    assert result.selected == ["e"]
    assert result.total_cost == pytest.approx(3000.0)


# ── Shadow prices monotonic (non-increasing) in budget ───────────────────────


def test_budget_shadow_price_monotonic():
    # Four €1000 benefits with descending satisfaction → diminishing returns, so
    # the per-€1000 budget shadow price must not increase as budget grows.
    candidates = [
        BenefitCandidate("i1", "c1", 1000, 10, variance=0),
        BenefitCandidate("i2", "c2", 1000, 8, variance=0),
        BenefitCandidate("i3", "c3", 1000, 6, variance=0),
        BenefitCandidate("i4", "c4", 1000, 4, variance=0),
    ]
    prices = []
    for budget in (1000, 2000, 3000):
        result = optimize(budget=budget, candidates=candidates, lambda_risk=0.0)
        assert result.feasible
        prices.append(result.shadow_prices["budget_per_1000"])
    assert prices == sorted(prices, reverse=True), prices
    assert prices[0] > prices[-1]  # genuinely diminishing, not all equal


# ── Determinism: same request → identical serialized bytes ───────────────────


def _serialize(result) -> str:
    return json.dumps(
        {
            "selected": result.selected,
            "achieved_utility": result.achieved_utility,
            "total_cost": result.total_cost,
            "shadow_prices": result.shadow_prices,
        },
        sort_keys=True,
    )


def test_deterministic_output():
    a = optimize(budget=8000, candidates=_toy_three(), lambda_risk=0.1)
    b = optimize(budget=8000, candidates=_toy_three(), lambda_risk=0.1)
    assert _serialize(a) == _serialize(b)


# ── Input validation ─────────────────────────────────────────────────────────


def test_lambda_out_of_bounds_raises():
    with pytest.raises(OptimizationError):
        optimize(budget=1000, candidates=_toy_three(), lambda_risk=9.0)


def test_unknown_mandatory_id_raises():
    with pytest.raises(OptimizationError):
        optimize(budget=8000, candidates=_toy_three(), mandatory_ids=["zzz"])
