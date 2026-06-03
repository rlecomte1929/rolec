"""Markowitz-style benefit-mix portfolio optimizer (Parker-B).

Given an HR company's relocation budget and a set of candidate benefits, pick the
binary mix that maximizes a mean-variance utility

    U = Σ_i x_i · expected_satisfaction_i  −  λ · Σ_i x_i · variance_i

subject to:
  * total budget      Σ_i x_i · cost_i ≤ budget
  * mandatory set     x_i = 1  for i in mandatory_ids
  * per-category cap  Σ_{i∈c} x_i · cost_i ≤ cap_c
  * minimum coverage  Σ_i x_i ≥ min_coverage

The selection is binary (a benefit is in the mix or not), so this is a small
mixed-integer linear program. We solve it with PuLP's bundled CBC backend.

`optimize()` is a pure function over its inputs — no DB access — so it is unit
testable in isolation. PuLP is imported lazily inside the solve so importing this
module never requires the solver to be installed (mirrors the Parker-A lifelines
pattern; the test module guards with ``pytest.importorskip("pulp")``).

Shadow prices are computed by **finite-difference sensitivity**, not LP duals: an
integer program has no well-defined dual, so we re-solve at a relaxed bound and
report the change in achieved utility per relaxed unit. That is exactly the
"each extra €1000 of budget yields +X satisfaction" artefact HR buyers want, and
it is deterministic.

Determinism: candidates are sorted by id before the model is built, CBC runs
single-threaded, and all numeric outputs are rounded to a fixed precision before
serialization, so the same request yields byte-identical output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Default coefficient-of-variation 0.5 → var = 0.25 · expected² when no prior exists.
DEFAULT_CV = 0.5

# Risk-aversion bounds (λ). 0 = pure satisfaction maximization.
LAMBDA_MIN = 0.0
LAMBDA_MAX = 5.0
DEFAULT_LAMBDA = 0.3

# Budget shadow price is reported per this many currency units ("+X per €1000").
BUDGET_SHADOW_STEP = 1000.0

# Rounding precision for deterministic serialization.
_ROUND = 6


class OptimizationError(ValueError):
    """Raised for malformed optimizer inputs (bad λ, negative budget, etc.)."""


def default_variance(expected_satisfaction: float) -> float:
    """Prior variance when none is supplied: CV 0.5 → ``0.25 · expected²``."""
    return (DEFAULT_CV ** 2) * float(expected_satisfaction) ** 2


@dataclass(frozen=True)
class BenefitCandidate:
    """A single candidate benefit the optimizer may select."""

    id: str
    category: str
    cost_per_employee: float
    expected_satisfaction: float
    variance: Optional[float] = None
    mandatory: bool = False
    hard_constraints: Dict[str, object] = field(default_factory=dict)

    def effective_variance(self) -> float:
        if self.variance is None:
            return default_variance(self.expected_satisfaction)
        return float(self.variance)

    def utility(self, lambda_risk: float) -> float:
        """Marginal utility contribution if selected."""
        return float(self.expected_satisfaction) - lambda_risk * self.effective_variance()


@dataclass(frozen=True)
class OptimizationResult:
    """Outcome of an :func:`optimize` call.

    ``selected`` is the ordered list of chosen candidate ids. ``shadow_prices`` maps
    constraint identifiers to the marginal utility unlocked by relaxing them:
      * ``"budget_per_1000"`` — extra utility per additional €1000 of budget.
      * ``"category_caps"`` — per-category extra utility per additional €1000 of cap.
      * ``"min_coverage"`` — extra utility from requiring one fewer benefit (≤ 0 when
        the coverage floor is binding and forcing low-utility picks).
    """

    feasible: bool
    selected: List[str] = field(default_factory=list)
    achieved_utility: float = 0.0
    total_cost: float = 0.0
    shadow_prices: Dict[str, object] = field(default_factory=dict)
    lambda_risk: float = DEFAULT_LAMBDA
    infeasibility_reason: Optional[str] = None


def _validate_inputs(
    budget: float,
    candidates: List[BenefitCandidate],
    lambda_risk: float,
    min_coverage: int,
) -> None:
    if budget < 0:
        raise OptimizationError("budget must be non-negative")
    if not (LAMBDA_MIN <= lambda_risk <= LAMBDA_MAX):
        raise OptimizationError(
            f"lambda_risk must be within [{LAMBDA_MIN}, {LAMBDA_MAX}], got {lambda_risk}"
        )
    if min_coverage < 0:
        raise OptimizationError("min_coverage must be non-negative")
    ids = [c.id for c in candidates]
    if len(ids) != len(set(ids)):
        raise OptimizationError("candidate ids must be unique")
    for c in candidates:
        if c.cost_per_employee < 0:
            raise OptimizationError(f"candidate {c.id} has negative cost")


def _mandatory_set(
    candidates: List[BenefitCandidate], mandatory_ids: Optional[List[str]]
) -> set:
    forced = {c.id for c in candidates if c.mandatory}
    if mandatory_ids:
        known = {c.id for c in candidates}
        for mid in mandatory_ids:
            if mid not in known:
                raise OptimizationError(f"mandatory id {mid!r} is not among candidates")
        forced |= set(mandatory_ids)
    return forced


def _precheck_infeasible(
    budget: float,
    candidates: List[BenefitCandidate],
    forced: set,
    category_caps: Dict[str, float],
) -> Optional[str]:
    """Cheap structural feasibility checks before invoking the solver."""
    by_id = {c.id: c for c in candidates}
    mandatory_cost = sum(by_id[i].cost_per_employee for i in forced)
    if mandatory_cost > budget:
        return "mandatory_exceeds_budget"

    # A mandatory benefit whose category cap cannot fit it is infeasible.
    cat_mandatory_cost: Dict[str, float] = {}
    for i in forced:
        cat = by_id[i].category
        cat_mandatory_cost[cat] = cat_mandatory_cost.get(cat, 0.0) + by_id[i].cost_per_employee
    for cat, spent in cat_mandatory_cost.items():
        if cat in category_caps and spent > category_caps[cat]:
            return "mandatory_exceeds_category_cap"
    return None


def _solve(
    budget: float,
    candidates: List[BenefitCandidate],
    forced: set,
    category_caps: Dict[str, float],
    lambda_risk: float,
    min_coverage: int,
) -> Optional[Tuple[List[str], float, float]]:
    """Solve the MILP. Returns (selected_ids, utility, total_cost) or None if infeasible."""
    import pulp  # lazy — keeps module import solver-free

    # Deterministic variable ordering.
    ordered = sorted(candidates, key=lambda c: c.id)
    prob = pulp.LpProblem("benefit_mix", pulp.LpMaximize)
    x = {c.id: pulp.LpVariable(f"x_{c.id}", cat="Binary") for c in ordered}

    prob += pulp.lpSum(c.utility(lambda_risk) * x[c.id] for c in ordered), "utility"

    prob += (
        pulp.lpSum(c.cost_per_employee * x[c.id] for c in ordered) <= budget,
        "budget",
    )
    for i in forced:
        prob += x[i] == 1, f"force_{i}"

    by_cat: Dict[str, List[BenefitCandidate]] = {}
    for c in ordered:
        by_cat.setdefault(c.category, []).append(c)
    for cat, cap in category_caps.items():
        members = by_cat.get(cat, [])
        if members:
            prob += (
                pulp.lpSum(c.cost_per_employee * x[c.id] for c in members) <= cap,
                f"cap_{cat}",
            )

    if min_coverage > 0:
        prob += pulp.lpSum(x[c.id] for c in ordered) >= min_coverage, "min_coverage"

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False, threads=1))
    if pulp.LpStatus[status] != "Optimal":
        return None

    selected = sorted(c.id for c in ordered if x[c.id].value() is not None and x[c.id].value() > 0.5)
    by_id = {c.id: c for c in ordered}
    utility = sum(by_id[i].utility(lambda_risk) for i in selected)
    total_cost = sum(by_id[i].cost_per_employee for i in selected)
    return selected, round(utility, _ROUND), round(total_cost, _ROUND)


def _budget_shadow_price(
    budget: float,
    candidates: List[BenefitCandidate],
    forced: set,
    category_caps: Dict[str, float],
    lambda_risk: float,
    min_coverage: int,
    base_utility: float,
) -> float:
    """Extra utility per +€BUDGET_SHADOW_STEP, via a forward finite difference."""
    bumped = _solve(
        budget + BUDGET_SHADOW_STEP, candidates, forced, category_caps, lambda_risk, min_coverage
    )
    if bumped is None:
        return 0.0
    return round(max(bumped[1] - base_utility, 0.0), _ROUND)


def _category_cap_shadow_prices(
    budget: float,
    candidates: List[BenefitCandidate],
    forced: set,
    category_caps: Dict[str, float],
    lambda_risk: float,
    min_coverage: int,
    base_utility: float,
) -> Dict[str, float]:
    """Per-category extra utility per +€BUDGET_SHADOW_STEP of that category's cap."""
    out: Dict[str, float] = {}
    for cat, cap in category_caps.items():
        relaxed = dict(category_caps)
        relaxed[cat] = cap + BUDGET_SHADOW_STEP
        bumped = _solve(budget, candidates, forced, relaxed, lambda_risk, min_coverage)
        out[cat] = 0.0 if bumped is None else round(max(bumped[1] - base_utility, 0.0), _ROUND)
    return out


def _min_coverage_shadow_price(
    budget: float,
    candidates: List[BenefitCandidate],
    forced: set,
    category_caps: Dict[str, float],
    lambda_risk: float,
    min_coverage: int,
    base_utility: float,
) -> float:
    """Utility change from requiring one fewer benefit (≤ 0 when the floor binds)."""
    if min_coverage <= 0:
        return 0.0
    relaxed = _solve(
        budget, candidates, forced, category_caps, lambda_risk, min_coverage - 1
    )
    if relaxed is None:
        return 0.0
    return round(relaxed[1] - base_utility, _ROUND)


def optimize(
    budget: float,
    candidates: List[BenefitCandidate],
    mandatory_ids: Optional[List[str]] = None,
    category_caps: Optional[Dict[str, float]] = None,
    lambda_risk: float = DEFAULT_LAMBDA,
    min_coverage: int = 0,
) -> OptimizationResult:
    """Return the utility-maximizing benefit mix and its shadow prices.

    Raises :class:`OptimizationError` on malformed inputs. Returns a result with
    ``feasible=False`` (and a structured ``infeasibility_reason``) when no mix can
    satisfy the constraints — it does not raise for infeasibility.
    """
    category_caps = dict(category_caps or {})
    _validate_inputs(budget, candidates, lambda_risk, min_coverage)
    forced = _mandatory_set(candidates, mandatory_ids)

    reason = _precheck_infeasible(budget, candidates, forced, category_caps)
    if reason is not None:
        return OptimizationResult(
            feasible=False, lambda_risk=lambda_risk, infeasibility_reason=reason
        )

    solved = _solve(budget, candidates, forced, category_caps, lambda_risk, min_coverage)
    if solved is None:
        return OptimizationResult(
            feasible=False, lambda_risk=lambda_risk, infeasibility_reason="no_feasible_mix"
        )

    selected, utility, total_cost = solved
    shadow = {
        "budget_per_1000": _budget_shadow_price(
            budget, candidates, forced, category_caps, lambda_risk, min_coverage, utility
        ),
        "category_caps": _category_cap_shadow_prices(
            budget, candidates, forced, category_caps, lambda_risk, min_coverage, utility
        ),
        "min_coverage": _min_coverage_shadow_price(
            budget, candidates, forced, category_caps, lambda_risk, min_coverage, utility
        ),
    }
    return OptimizationResult(
        feasible=True,
        selected=selected,
        achieved_utility=utility,
        total_cost=total_cost,
        shadow_prices=shadow,
        lambda_risk=lambda_risk,
    )
