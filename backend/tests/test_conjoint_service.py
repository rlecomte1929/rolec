"""
Tests for the conjoint analysis core — Parker Step H.

Fits an effects-coded conditional logit on a synthetic Sawtooth-style choice dataset
(generated from known part-worths via Gumbel-max MNL sampling — no licensed data) and
checks recovery quality, effects-coding properties, share simulation and the
budget-constrained recommender. numpy/scipy are required for the fit and are skipped
cleanly when absent.
"""
from __future__ import annotations

import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")

from backend.app.services import conjoint_service as svc  # noqa: E402


ATTRS = {
    "housing": ["none", "basic", "premium"],
    "tax": ["none", "full"],
    "language": ["none", "group", "private"],
}

# Ground-truth part-worths used to generate choices. housing dominates.
# Signal scaled so the (correctly MNL-specified) fit clears the McFadden
# excellent-fit floor with margin rather than sitting on the boundary.
TRUE_PW = {
    "housing": {"none": -1.4, "basic": 0.3, "premium": 1.1},
    "tax": {"none": -0.7, "full": 0.7},
    "language": {"none": -0.8, "group": 0.1, "private": 0.7},
}


def _utility(bundle, pw):
    return sum(pw[a][bundle[a]] for a in bundle)


def _simulate_dataset(n_respondents=250, n_sets=8, seed=7):
    """Generate MNL choices via Gumbel-max sampling from TRUE_PW."""
    rng = np.random.default_rng(seed)
    responses = []
    for r in range(n_respondents):
        sets = svc.design_study(ATTRS, n_sets, n_alts=3, seed=seed + r)
        for cs in sets:
            utils = np.array([_utility(b, TRUE_PW) for b in cs.alternatives])
            gumbel = rng.gumbel(size=len(utils))
            chosen = int(np.argmax(utils + gumbel))
            responses.append(svc.Response(choice_set=cs.alternatives, chosen_index=chosen))
    return responses


def test_fit_recovers_part_worths_and_meets_mcfadden_target():
    responses = _simulate_dataset()
    results = svc.fit_conjoint(ATTRS, responses)

    assert results.fit_quality["converged"] == 1.0
    assert results.fit_quality["n_obs"] == float(len(responses))
    # Standard Sawtooth-style synthetic target.
    assert results.fit_quality["mcfadden_r2"] >= 0.25

    pw = results.part_worths
    # Dominant attribute ordering is recovered: premium > basic > none.
    assert pw["housing"]["premium"] > pw["housing"]["basic"] > pw["housing"]["none"]
    assert pw["tax"]["full"] > pw["tax"]["none"]
    assert pw["language"]["private"] > pw["language"]["group"] > pw["language"]["none"]


def test_effects_coding_sums_to_zero_per_attribute():
    results = svc.fit_conjoint(ATTRS, _simulate_dataset(n_respondents=120))
    for attr, levels in results.part_worths.items():
        assert abs(sum(levels.values())) < 1e-6, attr


def test_no_responses_yields_zeroed_fit():
    results = svc.fit_conjoint(ATTRS, [])
    assert results.fit_quality["n_obs"] == 0.0
    assert results.fit_quality["converged"] == 0.0
    # Part-worths present but all zero.
    assert all(v == 0.0 for levels in results.part_worths.values() for v in levels.values())


def test_simulate_market_share_ranks_and_normalises():
    pw = TRUE_PW
    strong = {"housing": "premium", "tax": "full", "language": "private"}
    weak = {"housing": "none", "tax": "none", "language": "none"}
    shares = svc.simulate_market_share([strong, weak], pw, ids=["strong", "weak"])
    assert abs(sum(shares.values()) - 1.0) < 1e-9
    assert shares["strong"] > shares["weak"]


def test_recommend_bundle_respects_budget_and_constraints():
    costs = {
        "housing": {"none": 0.0, "basic": 1000.0, "premium": 3000.0},
        "tax": {"none": 0.0, "full": 1500.0},
        "language": {"none": 0.0, "group": 500.0, "private": 2000.0},
    }
    # Generous budget → should pick the all-premium bundle (max utility).
    best = svc.recommend_bundle(10000.0, costs, TRUE_PW)
    assert best == {"housing": "premium", "tax": "full", "language": "private"}

    # Tight budget forces cheaper levels; never exceeds budget.
    tight = svc.recommend_bundle(1200.0, costs, TRUE_PW)
    assert tight is not None
    spent = sum(costs[a][tight[a]] for a in tight)
    assert spent <= 1200.0

    # Hard constraint pins an attribute level.
    pinned = svc.recommend_bundle(
        10000.0, costs, TRUE_PW, hard_constraints={"housing": "basic"}
    )
    assert pinned is not None and pinned["housing"] == "basic"


def test_recommend_bundle_returns_none_when_nothing_affordable():
    costs = {"housing": {"none": 5000.0, "basic": 6000.0, "premium": 9000.0}}
    pw = {"housing": {"none": 0.0, "basic": 0.5, "premium": 1.0}}
    assert svc.recommend_bundle(100.0, costs, pw) is None


def test_design_study_shape_and_distinctness():
    sets = svc.design_study(ATTRS, 10, n_alts=3, seed=1)
    assert len(sets) == 10
    for cs in sets:
        assert len(cs.alternatives) == 3
        keys = {tuple(sorted(b.items())) for b in cs.alternatives}
        assert len(keys) == 3  # distinct within a set
        for b in cs.alternatives:
            for attr, lvl in b.items():
                assert lvl in ATTRS[attr]
