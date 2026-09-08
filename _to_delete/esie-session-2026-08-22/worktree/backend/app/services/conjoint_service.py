"""
Conjoint analysis core — Parker Step H.

Pure, DB-free choice-based-conjoint (CBC) math:

  * ``design_study``        — balanced randomised choice-set design over a level space.
  * ``fit_conjoint``        — aggregate conditional (multinomial) logit with **effects
                              coding**, fitted by maximum likelihood, returning per-
                              attribute-level part-worths + fit quality.
  * ``simulate_market_share`` — softmax of bundle utilities → predicted share.
  * ``recommend_bundle``    — utility-maximising bundle within budget + hard constraints.

Effects coding (not dummy coding) is used so part-worths are deviations from the grand
mean and sum to zero within each attribute — the interpretation HR readers expect.

numpy / scipy are lazy-imported inside ``fit_conjoint`` so this module imports cleanly in
environments without the numerical stack (the rest of the API still works); callers that
need a fit must have numpy + scipy installed (see ``statsmodels`` in requirements.txt,
which transitively provides them).
"""
from __future__ import annotations

import itertools
import logging
import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

# An offered benefit bundle: attribute name -> chosen level.
Bundle = Dict[str, str]
# attribute -> ordered list of levels.
Attributes = Dict[str, List[str]]
# attribute -> level -> part-worth (utility contribution).
PartWorths = Dict[str, Dict[str, float]]


@dataclass(frozen=True)
class ChoiceSet:
    """One screen shown to a respondent: a list of mutually-exclusive bundles."""

    alternatives: List[Bundle]


@dataclass(frozen=True)
class Response:
    """A respondent's pick: the bundles they saw and the index they chose."""

    choice_set: List[Bundle]
    chosen_index: int


@dataclass(frozen=True)
class ConjointResults:
    """Fitted part-worths plus goodness-of-fit diagnostics."""

    part_worths: PartWorths
    fit_quality: Dict[str, float]  # log_likelihood, mcfadden_r2, n_obs, converged


# --------------------------------------------------------------------------- #
# Design                                                                       #
# --------------------------------------------------------------------------- #


def design_study(
    attributes: Attributes,
    n_choice_sets: int,
    *,
    n_alts: int = 3,
    seed: Optional[int] = None,
) -> List[ChoiceSet]:
    """Generate ``n_choice_sets`` balanced-random choice sets of ``n_alts`` bundles each.

    A D-optimal design is overkill for an early-stage product claim (see the task notes):
    balanced randomisation over the full level space is more than sufficient. Each set
    holds distinct bundles; we cycle a shuffled pool of full-factorial profiles so every
    profile (and therefore every level) appears before any repeats.
    """
    if n_choice_sets <= 0:
        return []
    names = list(attributes.keys())
    level_lists = [attributes[a] for a in names]
    if not names or any(len(lv) == 0 for lv in level_lists):
        return []

    profiles: List[Bundle] = [
        dict(zip(names, combo)) for combo in itertools.product(*level_lists)
    ]
    alts = min(max(2, n_alts), len(profiles))
    rng = random.Random(seed)

    pool: List[Bundle] = []
    sets: List[ChoiceSet] = []
    for _ in range(n_choice_sets):
        chosen: List[Bundle] = []
        seen: set[Tuple[Tuple[str, str], ...]] = set()
        while len(chosen) < alts:
            if not pool:
                pool = list(profiles)
                rng.shuffle(pool)
            cand = pool.pop()
            key = tuple(sorted(cand.items()))
            if key in seen:
                continue
            seen.add(key)
            chosen.append(cand)
        sets.append(ChoiceSet(alternatives=chosen))
    return sets


# --------------------------------------------------------------------------- #
# Effects-coded encoder                                                        #
# --------------------------------------------------------------------------- #


class _Encoder:
    """Maps bundles to effects-coded feature vectors and back to part-worths.

    For an attribute with levels ``[l0, .., l_{k-1}]`` the last level is the reference.
    Each non-reference level gets one column: its own bundle → +1 on that column,
    the reference bundle → −1 on every column of that attribute.
    """

    def __init__(self, attributes: Attributes) -> None:
        self.attributes = attributes
        self.param_keys: List[Tuple[str, str]] = []
        self._col: Dict[Tuple[str, str], int] = {}
        self._ref: Dict[str, str] = {}
        self._attr_cols: Dict[str, List[int]] = {}
        for attr, levels in attributes.items():
            if len(levels) < 2:
                # A single-level attribute carries no information; skip it.
                self._ref[attr] = levels[0] if levels else ""
                self._attr_cols[attr] = []
                continue
            self._ref[attr] = levels[-1]
            cols: List[int] = []
            for lvl in levels[:-1]:
                idx = len(self.param_keys)
                self.param_keys.append((attr, lvl))
                self._col[(attr, lvl)] = idx
                cols.append(idx)
            self._attr_cols[attr] = cols

    @property
    def n_params(self) -> int:
        return len(self.param_keys)

    def encode(self, bundle: Bundle) -> List[float]:
        vec = [0.0] * self.n_params
        for attr, levels in self.attributes.items():
            if len(levels) < 2:
                continue
            lvl = bundle.get(attr)
            if lvl == self._ref[attr]:
                for c in self._attr_cols[attr]:
                    vec[c] = -1.0
            elif (attr, lvl) in self._col:
                vec[self._col[(attr, lvl)]] = 1.0
        return vec

    def part_worths(self, beta: Sequence[float]) -> PartWorths:
        out: PartWorths = {}
        for attr, levels in self.attributes.items():
            if len(levels) < 2:
                out[attr] = {levels[0]: 0.0} if levels else {}
                continue
            pw: Dict[str, float] = {}
            ref_val = 0.0
            for lvl in levels[:-1]:
                v = float(beta[self._col[(attr, lvl)]])
                pw[lvl] = v
                ref_val -= v
            pw[self._ref[attr]] = ref_val  # effects coding → sums to zero
            out[attr] = pw
        return out


# --------------------------------------------------------------------------- #
# Fit (conditional logit, MLE)                                                 #
# --------------------------------------------------------------------------- #


def fit_conjoint(attributes: Attributes, responses: Sequence[Response]) -> ConjointResults:
    """Fit an aggregate effects-coded conditional logit by maximum likelihood.

    For a choice set with chosen alternative ``c``:
    ``LL += xᵀc·β − logsumexp_j(xᵀj·β)``. Maximised via ``scipy.optimize.minimize`` with
    an analytic gradient. McFadden R² compares the fitted log-likelihood against the
    equal-probability null. Never raises: a numerical failure yields zeroed part-worths
    with ``converged=False`` so the calling endpoint stays a 200.
    """
    enc = _Encoder(attributes)
    valid = [r for r in responses if r.choice_set and 0 <= r.chosen_index < len(r.choice_set)]
    n_obs = len(valid)
    zeroed = ConjointResults(
        part_worths=enc.part_worths([0.0] * enc.n_params),
        fit_quality={"log_likelihood": 0.0, "mcfadden_r2": 0.0, "n_obs": float(n_obs), "converged": 0.0},
    )
    if n_obs == 0 or enc.n_params == 0:
        return zeroed

    try:
        import numpy as np
        from scipy.optimize import minimize

        designs: List[Tuple[Any, int]] = []
        ll_null = 0.0
        for r in valid:
            X = np.array([enc.encode(b) for b in r.choice_set], dtype=float)
            designs.append((X, r.chosen_index))
            ll_null -= math.log(len(r.choice_set))

        def neg_ll_grad(beta: Any) -> Tuple[float, Any]:
            ll = 0.0
            grad = np.zeros(enc.n_params)
            for X, c in designs:
                u = X @ beta
                m = float(u.max())
                shifted = u - m
                denom = m + math.log(float(np.exp(shifted).sum()))
                ll += float(u[c]) - denom
                p = np.exp(u - denom)
                grad += X[c] - p @ X
            return -ll, -grad

        res = minimize(
            neg_ll_grad,
            np.zeros(enc.n_params),
            jac=True,
            method="BFGS",
            options={"maxiter": 300, "gtol": 1e-6},
        )
        beta = res.x
        ll_model = -float(neg_ll_grad(beta)[0])
        mcfadden = 1.0 - (ll_model / ll_null) if ll_null != 0 else 0.0
        return ConjointResults(
            part_worths=enc.part_worths(beta),
            fit_quality={
                "log_likelihood": round(ll_model, 6),
                "mcfadden_r2": round(mcfadden, 6),
                "n_obs": float(n_obs),
                "converged": 1.0 if bool(res.success) else 0.0,
            },
        )
    except Exception:
        log.exception("conjoint fit failed — returning zeroed part-worths")
        return zeroed


# --------------------------------------------------------------------------- #
# Simulation + recommendation                                                  #
# --------------------------------------------------------------------------- #


def _bundle_utility(bundle: Bundle, part_worths: PartWorths) -> float:
    total = 0.0
    for attr, lvl in bundle.items():
        total += float(part_worths.get(attr, {}).get(lvl, 0.0))
    return total


def simulate_market_share(
    bundles: Sequence[Bundle],
    part_worths: PartWorths,
    *,
    ids: Optional[Sequence[str]] = None,
) -> Dict[str, float]:
    """Predicted share for each bundle = softmax over total bundle utilities."""
    if not bundles:
        return {}
    keys = list(ids) if ids is not None else [f"bundle_{i}" for i in range(len(bundles))]
    utils = [_bundle_utility(b, part_worths) for b in bundles]
    m = max(utils)
    exps = [math.exp(u - m) for u in utils]
    denom = sum(exps) or 1.0
    return {k: e / denom for k, e in zip(keys, exps)}


def recommend_bundle(
    budget: float,
    attribute_costs: Dict[str, Dict[str, float]],
    part_worths: PartWorths,
    hard_constraints: Optional[Dict[str, Any]] = None,
) -> Optional[Bundle]:
    """Return the budget-feasible bundle with the highest total utility, or ``None``.

    ``attribute_costs[attr][level]`` is the per-employee cost of that level.
    ``hard_constraints[attr]`` may be a single required level or an iterable of allowed
    levels; attributes absent from the constraints are free. Enumerates the level space
    defined by ``part_worths`` (small by construction in early-stage studies).
    """
    constraints = hard_constraints or {}
    attrs = list(part_worths.keys())
    level_options: List[List[str]] = []
    for attr in attrs:
        levels = list(part_worths[attr].keys())
        if attr in constraints:
            req = constraints[attr]
            allowed = {req} if isinstance(req, str) else set(req)
            levels = [lv for lv in levels if lv in allowed]
        if not levels:
            return None  # an attribute's constraint excludes every level
        level_options.append(levels)

    best: Optional[Bundle] = None
    best_util = -math.inf
    for combo in itertools.product(*level_options):
        bundle: Bundle = dict(zip(attrs, combo))
        cost = sum(
            float(attribute_costs.get(a, {}).get(lvl, 0.0)) for a, lvl in bundle.items()
        )
        if cost > budget:
            continue
        util = _bundle_utility(bundle, part_worths)
        if util > best_util:
            best_util = util
            best = bundle
    return best
