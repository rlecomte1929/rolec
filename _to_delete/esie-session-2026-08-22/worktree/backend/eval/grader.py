"""Shared offline-eval aggregator + lightweight gate registry.

Each individual eval runner (``run_refusal_eval``, ``run_pii_eval``, …) already
exposes a ``run_eval(...) -> dict`` carrying a ``gate_pass`` bool plus lists of
failing case ids. What was missing is ONE entrypoint that runs every
*offline / hermetic* gate (no network, committed fixtures) and returns a single
combined, machine-readable report — the input to :mod:`backend.eval.error_analysis`
and to a one-line "are all AI eval gates green?" check.

Scope — offline gates only
--------------------------
Only gates that are deterministic, network-free, and backed by a committed,
*non-vacuous* fixture set are registered here. The corpus-backed runners
(``run_eligibility_eval``, ``run_contradiction_eval``, ``run_extraction_eval``)
are intentionally excluded until a real ``ground_truth.json`` corpus is committed
for them — running them against an empty corpus reports a vacuous pass and would
make this aggregator lie. Register them here (see ``OFFLINE_GATES``) the moment a
non-vacuous corpus lands.

This module does NOT rewrite the existing runners; it wraps their public
``run_eval`` + ``DEFAULT_FIXTURES`` so they stay the single source of truth for
their own thresholds and fixtures.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List

from . import run_pii_eval, run_refusal_eval


@dataclass
class GateResult:
    """Normalised result of one offline eval gate.

    Attributes
    ----------
    name:     short gate id (e.g. ``"refusal"``).
    module:   which product module it guards (``immigration`` | ``hr_policy`` |
              ``supplier`` | ``shared``) — lets error analysis group by module.
    passed:   the runner's own ``gate_pass`` verdict.
    headline: a few key scalar metrics for the summary table.
    failing:  failure-type -> list of failing case ids (the runner's own lists).
    cases:    per-case rows (case_id, category, expected, actual, passed) used to
              build a confusion matrix. May be empty for gates that don't expose
              per-case detail.
    """

    name: str
    module: str
    passed: bool
    headline: Dict[str, object] = field(default_factory=dict)
    failing: Dict[str, List[str]] = field(default_factory=dict)
    cases: List[Dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "module": self.module,
            "passed": self.passed,
            "headline": self.headline,
            "failing": self.failing,
            "cases": self.cases,
        }


def _refusal_gate() -> GateResult:
    """Wrap AIQ-601 refusal-correctness (policy assistant)."""
    report = run_refusal_eval.run_eval(run_refusal_eval.DEFAULT_FIXTURES)
    cases = [
        {
            "case_id": r.case_id,
            "category": r.category,
            # expected = should the assistant refuse this prompt?
            "expected": "refuse" if r.expected == "refuse" else "answer",
            "actual": "refuse" if r.actually_refused else "answer",
            "passed": r.passed,
        }
        for r in report["results"]
    ]
    return GateResult(
        name="refusal",
        module="hr_policy",
        passed=bool(report["gate_pass"]),
        headline={
            "refusal_recall": round(float(report["refusal_recall"]), 4),
            "threshold": report["threshold"],
            "n_should_refuse": report["n_should_refuse"],
            "n_controls": report["n_controls"],
        },
        failing={
            "missed_refusals": list(report["missed_refusals"]),
            "over_refusals": list(report["over_refusals"]),
            "code_mismatches": list(report["code_mismatches"]),
        },
        cases=cases,
    )


def _pii_gate() -> GateResult:
    """Wrap AIQ-602 PII-leak / cross-tier-fence (policy assistant)."""
    report = run_pii_eval.run_eval(run_pii_eval.DEFAULT_FIXTURES)
    cases = [
        {
            "case_id": r.case_id,
            "category": r.category,
            # expected = every prompt in this corpus should be blocked.
            "expected": "block",
            "actual": "block" if r.blocked else "leak",
            "passed": r.passed,
        }
        for r in report["results"]
    ]
    return GateResult(
        name="pii_leak",
        module="hr_policy",
        passed=bool(report["gate_pass"]),
        headline={
            "leak_count": report["leak_count"],
            "n_cases": report["n_cases"],
        },
        failing={
            "leaks": list(report["leaks"]),
            "uncoded_blocks": list(report["uncoded_blocks"]),
        },
        cases=cases,
    )


# Registry of offline, non-vacuous gates. Append corpus-backed gates here once a
# real corpus is committed (e.g. a lambda running run_eligibility_eval over
# backend/tests/fixtures/eligibility with the real predictor).
OFFLINE_GATES: List[Callable[[], GateResult]] = [
    _refusal_gate,
    _pii_gate,
]


def run_all_offline_gates() -> Dict[str, object]:
    """Run every registered offline gate and return a combined report."""
    gates = [factory() for factory in OFFLINE_GATES]
    return {
        "all_passed": all(g.passed for g in gates),
        "n_gates": len(gates),
        "n_failed": sum(1 for g in gates if not g.passed),
        "gates": [g.to_dict() for g in gates],
    }
