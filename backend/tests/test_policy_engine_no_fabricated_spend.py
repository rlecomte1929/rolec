"""AIQ-2087 — the policy engine must not invent spend.

THE BUG
-------
`PolicyEngine.compute_spend` SYNTHESISED per-category utilisation from a hash of
the case id:

    seed = sum(ord(ch) for ch in assignment_id) % 1000
    housing_used = int(housing_cap * 0.64 + (seed % 600))

against caps read from a checked-in `backend/policy_config.json` — one static file,
no company parameter, so every tenant saw the same $5k/$10k/$20k/$4k while their
real policy sat in `policy_config_benefits` (21,662 rows).

It reached HR three ways, and the third is the dangerous one:
  1. the `spend` block on GET /api/hr/policy?caseId=;
  2. `build_compliance_report` turned each item into a COMPLIANCE CHECK
     ("Housing over policy cap", FAIL/CRITICAL) which also feeds summary.riskScore;
  3. `over_limit` drove gating.requiresAcknowledgement / requiresHRApproval — a hash
     decided whether a case needed HR sign-off.

Same class as AIQ-1527 (test_budget_summary_honest.py): asserting something never
measured. There is no actuals source in the platform — `case_budget_lines` holds 0
rows — so the honest answer is no categories at all.

Every test here fails against the pre-AIQ-2087 engine.
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.policy_engine import PolicyEngine  # noqa: E402

_POLICY = {
    "caps": {
        "housing": {"amount": 5000, "currency": "USD"},
        "movers": {"amount": 10000, "currency": "USD"},
        "schools": {"amount": 20000, "currency": "USD"},
        "immigration": {"amount": 4000, "currency": "USD"},
    },
    "documentRequirements": {"base": []},
    "leadTimeRules": {"minDays": 30},
}
_PROFILE = {
    "movePlan": {"destination": "New York", "targetArrivalDate": "2026-10-01"},
    "spouse": {"fullName": "A Spouse"},
    "dependents": [{"name": "kid1"}, {"name": "kid2"}],
    "complianceDocs": {},
    "primaryApplicant": {},
}


def test_compute_spend_returns_no_categories():
    """No actuals source exists, so the only honest answer is nothing."""
    assert PolicyEngine().compute_spend("case-abc", _PROFILE, _POLICY) == {}


def test_compute_spend_does_not_vary_with_the_case_id():
    """The tell for the old bug: output was a function of the id's character sum.

    'ab' and 'ba' hash identically while 'ab' and 'ac' do not — so this both proves
    the hash is gone and would have caught it.
    """
    engine = PolicyEngine()
    outputs = [
        engine.compute_spend(cid, _PROFILE, _POLICY)
        for cid in ("ab", "ba", "ac", "zzzzzzzz", "")
    ]
    assert all(o == outputs[0] for o in outputs)


def test_compute_spend_does_not_vary_with_destination_or_family_size():
    """The old version multiplied by 1.18 for New York and 0.92 for a family > 2."""
    engine = PolicyEngine()
    solo = {**_PROFILE, "movePlan": {"destination": "Oslo"}, "spouse": {}, "dependents": []}
    assert engine.compute_spend("c1", solo, _POLICY) == engine.compute_spend("c1", _PROFILE, _POLICY)


def test_policy_response_carries_no_spend_and_gates_on_nothing_invented():
    """requiresHRApproval must not be a function of a hashed number."""
    out = PolicyEngine().build_policy_response("case-abc", _PROFILE, _POLICY, [])
    assert out["spend"] == {}
    assert out["gating"]["requiresAcknowledgement"] is False
    assert out["gating"]["requiresHRApproval"] is False


def test_gating_still_reflects_a_real_pending_exception():
    """Removing the fiction must not disarm the real gate.

    policy_cap_requests is a real table (5 rows in prod); a pending request there
    still requires HR approval.
    """
    out = PolicyEngine().build_policy_response(
        "case-abc", _PROFILE, _POLICY, [{"category": "housing", "status": "pending"}]
    )
    assert out["gating"]["requiresHRApproval"] is True


def test_compliance_report_emits_no_cap_checks():
    """The fabricated amounts became FAIL/CRITICAL compliance checks; they must go."""
    engine = PolicyEngine()
    spend = engine.compute_spend("case-abc", _PROFILE, _POLICY)
    report = engine.build_compliance_report("case-abc", _PROFILE, _POLICY, spend, [])
    # The field is `checkId`, not `id`. Asserting on `id` here silently matched
    # nothing and passed against the OLD engine too — caught only by re-running
    # these tests against origin/main's source. Pin the real key.
    assert all("checkId" in c for c in report["checks"]), "check shape changed"
    cap_checks = [c["checkId"] for c in report["checks"] if c["checkId"].endswith("_cap")]
    assert cap_checks == [], f"cap checks derived from invented spend: {cap_checks}"
    # The rest of the report (documents, lead time, …) still works.
    assert report["checks"], "report should still contain non-spend checks"
