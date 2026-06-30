"""
Real eligibility predictor for run_eligibility_eval.

Composes the deterministic ``ImmigrationRegimeRouter`` (backend/app/services/
immigration_regime.py) into the predictor protocol that ``run_eligibility_eval``
expects: a ``Callable[[dict], dict]`` that, given a ground-truth dossier, returns an
``eligibility_verdict``-shaped dict ``{"outcome_set": [...], "citations": [...]}``.

Crucially, the predictor reads ONLY the dossier's ``profile`` block (nationality,
origin/destination country, contract type) — it never looks at the ground-truth
``eligibility_verdict``. That makes the eval non-vacuous: the predictor independently
derives the outcome from the route and is then graded against the held-out truth.

Outcomes are derived from the router's ``regime_id``; citations are the rule-version
IDs that actually govern the matched route AND are present in
``backend/eval/rule_registry.py`` (so the citation-effectiveness gate is meaningful).
Routes with no registry-backed rule yet emit no citations rather than fabricating one
— honest under-coverage rather than a false cite. All five seed corridors (incl. the
France/Portugal work-permit routes) are now registry-backed with representative cites.
"""
from __future__ import annotations

from typing import Any, Dict, List

from backend.app.services.immigration_regime import ImmigrationRegimeRouter

_router = ImmigrationRegimeRouter()

# regime_id → eligibility outcome code. These are the verdict labels the eval grades
# predicted outcomes against (predicted ⊆ ground-truth outcome_set).
_REGIME_OUTCOME: Dict[str, str] = {
    "us_l1b": "ELIGIBLE_L1B_INTRACOMPANY",
    "japan_coe": "ELIGIBLE_JAPAN_COE",
    "uk_skilled_worker": "ELIGIBLE_UK_SKILLED_WORKER",
    "eu_free_movement": "ELIGIBLE_EU_FREE_MOVEMENT",
    "standard_work_permit": "ELIGIBLE_WORK_PERMIT",
    "domestic": "NO_IMMIGRATION_REQUIRED",
    "unknown": "INDETERMINATE",
}


def _citations_for(regime_id: str, destination_norm: str) -> List[str]:
    """Return rule-version IDs that govern this route and exist in the rule registry.

    Only registry-backed rules are emitted so ``run_eligibility_eval``'s
    citation-effectiveness check is meaningful. Routes without registry coverage
    return ``[]`` (vacuously passes the citation gate; surfaces as n_has_citation=0).
    """
    if regime_id == "eu_free_movement":
        cites = ["EU_DIR_2004_38_ART7:2004"]  # Free Movement Directive, Art. 7 (residence > 3 months)
        if destination_norm in {"norway", "no"}:
            cites.append("NO_EOS_UTLENDINGS:2010")  # Norway EEA residence regulations
        return cites
    if regime_id == "standard_work_permit":
        if destination_norm in {"germany", "de"}:
            return ["DE_AUFENTHG_18B:2020"]  # AufenthG §18b — skilled-worker residence permit
        if destination_norm in {"france", "fr"}:
            return ["FR_CESEDA_L421:2021"]  # CESEDA L.421 — "salarié" work/residence permit; in force 2021-05-01 (Ord. 2020-1733)
        if destination_norm in {"portugal", "pt"}:
            return ["PT_LEI_23_2007_ART88:2007"]  # Lei 23/2007 art. 88 — subordinate-work residence permit (representative)
    return []


def predict_eligibility(ground_truth: Dict[str, Any]) -> Dict[str, Any]:
    """Predictor entry point — matches run_eligibility_eval's predictor protocol.

    Reads ``ground_truth["profile"]`` (NOT the verdict) and returns
    ``{"outcome_set": [...], "citations": [...]}``.
    """
    profile = ground_truth.get("profile") or {}
    result = _router.detect_regime(
        nationality=profile.get("nationality"),
        destination_country=profile.get("destination_country"),
        origin_country=profile.get("origin_country"),
        contract_type=profile.get("contract_type"),
    )
    destination_norm = (profile.get("destination_country") or "").strip().lower()
    outcome = _REGIME_OUTCOME.get(result.regime_id, "INDETERMINATE")
    return {
        "outcome_set": [outcome],
        "citations": _citations_for(result.regime_id, destination_norm),
    }
