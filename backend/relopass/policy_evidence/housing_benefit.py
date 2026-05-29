"""HOUSING_BENEFIT evidence check (C2-06).

Architecture Report §6.1 — HOUSING_BENEFIT parameters:
    temporary_or_permanent    enum   — "TEMPORARY" | "PERMANENT" | "BOTH"
    duration_months           int    — max coverage duration
    monthly_cap               number — per-month spend cap
    currency                  str    — ISO 4217
    family_coverage_bool      bool   — covers family or employee-only

Evidence artefact (any of these clears the gap):
    kind='housing_booking'           — vendor booking for temporary housing
    kind='housing_lease_document'    — signed long-term lease on the case
    kind='housing_invoice'           — paid invoice from a housing vendor

Gap emission:
    MISSING_BENEFIT_DELIVERY  when no housing artefact of any of the three
                              kinds exists on the case for the applicable
                              subject set
    Sub-conditions (BELOW_ENTITLEMENT) are NOT implemented in C2-06; the
    monthly_cap + duration_months thresholds are auditable but not
    automatically tested here (deferred to a follow-up that needs invoice-
    line-item parsing).
"""

from __future__ import annotations

from typing import Any, ClassVar, Mapping, Optional, Sequence

from ._models import Artefact, Case, GapType, PolicyClause, Subject
from .base import EvidenceCheck
from .registry import register


class HousingBenefitEvidence(EvidenceCheck):
    clause_type: ClassVar[str] = "HOUSING_BENEFIT"
    default_gap_type: ClassVar[GapType] = "MISSING_BENEFIT_DELIVERY"
    ACCEPTED_KINDS: ClassVar["tuple[str, ...]"] = (
        "housing_booking",
        "housing_lease_document",
        "housing_invoice",
    )

    def applicable_subjects(
        self, clause: PolicyClause, case: Case
    ) -> Sequence[Subject]:
        return (Subject(kind="CASE"),)

    def evidence_for_subject(
        self, subject: Subject, clause: PolicyClause, case: Case
    ) -> Optional[Mapping[str, Any]]:
        artefacts = self._housing_artefacts(case)
        if not artefacts:
            return None
        kinds = {a.kind for a in artefacts}
        return {
            "artefact_kinds": sorted(kinds),
            "count": len(artefacts),
            "artefacts": [
                {
                    "artefact_id": str(a.artefact_id),
                    "kind": a.kind,
                    "delivered_at": a.delivered_at.isoformat()
                    if a.delivered_at
                    else None,
                    "magnitude": a.magnitude,
                    "unit": a.unit,
                }
                for a in artefacts
            ],
        }

    def suggested_action_for(
        self, subject: Subject, clause: PolicyClause, case: Case
    ) -> str:
        params = clause.parameters_json
        kind = params.get("temporary_or_permanent", "housing")
        cap = params.get("monthly_cap")
        currency = params.get("currency", "")
        cap_str = f" up to {cap} {currency}/month" if cap else ""
        return (
            f"Book {kind.lower()} housing for the case{cap_str} "
            f"per clause {clause.policy_clause_id}."
        )

    def _housing_artefacts(self, case: Case) -> "tuple[Artefact, ...]":
        results = []
        for k in self.ACCEPTED_KINDS:
            results.extend(case.find_artefacts(kind=k))
        return tuple(results)


register(HousingBenefitEvidence())
