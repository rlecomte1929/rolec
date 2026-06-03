"""IMMIGRATION_SUPPORT evidence check (C2-06).

Architecture Report §6.1 — IMMIGRATION_SUPPORT parameters:
    legal_fees_covered_bool         bool — employer pays immigration counsel
    permit_application_fees_bool    bool — employer covers government fees
    dependent_permits_bool          bool — coverage extends to family members

Per-subject scope:
    Always applies to EMPLOYEE.
    Applies to SPOUSE + CHILD + DEPENDENT_PARENT iff dependent_permits_bool.
    (Spouses / children / dependents need their own permit applications;
    the clause promises ReloPass + the employer will support them.)

Evidence artefact (any of these clears the gap):
    kind='permit_application_submitted'   — application filed with the
                                            receiving authority
    kind='legal_counsel_engaged'          — outside counsel engaged

The check is satisfied if EITHER artefact exists for the subject. The
intent: the policy promises "we will help" — the gap closes the moment
either form of help is on record. Subsequent stages (decision, card
issuance) are tracked separately by the corridor agent's StepGraph.
"""

from __future__ import annotations

from typing import Any, ClassVar, Mapping, Optional, Sequence

from ._models import Artefact, Case, GapType, PolicyClause, Subject
from .base import EvidenceCheck
from .registry import register


class ImmigrationSupportEvidence(EvidenceCheck):
    clause_type: ClassVar[str] = "IMMIGRATION_SUPPORT"
    default_gap_type: ClassVar[GapType] = "MISSING_BENEFIT_DELIVERY"
    ACCEPTED_KINDS: ClassVar["tuple[str, ...]"] = (
        "permit_application_submitted",
        "legal_counsel_engaged",
    )

    def applicable_subjects(
        self, clause: PolicyClause, case: Case
    ) -> Sequence[Subject]:
        subjects = [
            Subject(
                kind="EMPLOYEE",
                family_member_id=None,
                canonical_entity_id=case.primary_employee_canonical_id,
                display_name=case.primary_employee_display_name,
            )
        ]
        if clause.parameters_json.get("dependent_permits_bool"):
            for fm in case.family_members:
                subjects.append(
                    Subject(
                        kind=_subject_kind_for_relationship(fm.relationship_type),
                        family_member_id=fm.family_member_id,
                        canonical_entity_id=fm.canonical_entity_id,
                        display_name=fm.display_name,
                    )
                )
        return tuple(subjects)

    def evidence_for_subject(
        self, subject: Subject, clause: PolicyClause, case: Case
    ) -> Optional[Mapping[str, Any]]:
        artefacts = self._support_artefacts_for(case, subject)
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
                }
                for a in artefacts
            ],
        }

    def suggested_action_for(
        self, subject: Subject, clause: PolicyClause, case: Case
    ) -> str:
        labels = {
            "EMPLOYEE": "the employee",
            "SPOUSE": "the spouse",
            "CHILD": "the child",
            "DEPENDENT_PARENT": "the dependent parent",
            "CASE": "this case",
        }
        label = subject.display_name or labels.get(subject.kind, subject.kind.lower())
        return (
            f"Submit the permit application or engage immigration counsel for "
            f"{label} per clause {clause.policy_clause_id}."
        )

    def _support_artefacts_for(
        self, case: Case, subject: Subject
    ) -> "tuple[Artefact, ...]":
        results = []
        for k in self.ACCEPTED_KINDS:
            results.extend(
                case.find_artefacts(kind=k, family_member_id=subject.family_member_id)
            )
        return tuple(results)


def _subject_kind_for_relationship(rel: str) -> str:
    if rel == "SPOUSE":
        return "SPOUSE"
    if rel == "CHILD":
        return "CHILD"
    if rel == "DEPENDENT_PARENT":
        return "DEPENDENT_PARENT"
    raise ValueError(f"Unknown relationship_type: {rel}")


register(ImmigrationSupportEvidence())
