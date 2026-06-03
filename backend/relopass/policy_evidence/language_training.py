"""LANGUAGE_TRAINING evidence check (C2-06).

Architecture Report §6.1 — LANGUAGE_TRAINING parameters:
    hours                int     — total entitlement, e.g. 60
    target_cefr_level    str     — e.g. "B1"
    for_employee_bool    bool    — applies to the employee
    for_spouse_bool      bool    — applies to spouse
    for_children_bool    bool    — applies to each child

Evidence artefact:
    kind='language_training_booking'
    magnitude=<hours booked>
    unit='hours'
    payload={'cefr_level': '...', 'provider': '...', 'booking_id': '...'}

Gap emission:
    MISSING_BENEFIT_DELIVERY  when no booking artefact exists for the subject
    BELOW_ENTITLEMENT         when bookings exist but hours sum < policy hours
"""

from __future__ import annotations

from typing import Any, ClassVar, Mapping, Optional, Sequence

from ._models import Artefact, Case, GapType, PolicyClause, Subject
from .base import EvidenceCheck
from .registry import register


class LanguageTrainingEvidence(EvidenceCheck):
    clause_type: ClassVar[str] = "LANGUAGE_TRAINING"
    default_gap_type: ClassVar[GapType] = "MISSING_BENEFIT_DELIVERY"
    ARTEFACT_KIND: ClassVar[str] = "language_training_booking"

    def applicable_subjects(
        self, clause: PolicyClause, case: Case
    ) -> Sequence[Subject]:
        subjects = []
        params = clause.parameters_json
        if params.get("for_employee_bool"):
            subjects.append(
                Subject(
                    kind="EMPLOYEE",
                    family_member_id=None,
                    canonical_entity_id=case.primary_employee_canonical_id,
                    display_name=case.primary_employee_display_name,
                )
            )
        if params.get("for_spouse_bool"):
            for fm in case.family_by_relationship("SPOUSE"):
                subjects.append(
                    Subject(
                        kind="SPOUSE",
                        family_member_id=fm.family_member_id,
                        canonical_entity_id=fm.canonical_entity_id,
                        display_name=fm.display_name,
                    )
                )
        if params.get("for_children_bool"):
            for fm in case.family_by_relationship("CHILD"):
                subjects.append(
                    Subject(
                        kind="CHILD",
                        family_member_id=fm.family_member_id,
                        canonical_entity_id=fm.canonical_entity_id,
                        display_name=fm.display_name,
                    )
                )
        return tuple(subjects)

    def evidence_for_subject(
        self, subject: Subject, clause: PolicyClause, case: Case
    ) -> Optional[Mapping[str, Any]]:
        bookings = self._bookings_for(case, subject)
        if not bookings:
            return None
        required = float(clause.parameters_json.get("hours", 0) or 0)
        booked = sum((b.magnitude or 0) for b in bookings)
        if required and booked < required:
            return None
        return {
            "total_hours": booked,
            "booking_count": len(bookings),
            "bookings": [
                {
                    "artefact_id": str(b.artefact_id),
                    "magnitude": b.magnitude,
                    "delivered_at": b.delivered_at.isoformat()
                    if b.delivered_at
                    else None,
                    "payload": dict(b.payload),
                }
                for b in bookings
            ],
        }

    def gap_type_for(
        self, subject: Subject, clause: PolicyClause, case: Case
    ) -> GapType:
        if self._bookings_for(case, subject):
            return "BELOW_ENTITLEMENT"
        return "MISSING_BENEFIT_DELIVERY"

    def suggested_action_for(
        self, subject: Subject, clause: PolicyClause, case: Case
    ) -> str:
        params = clause.parameters_json
        hours = params.get("hours", "the contracted")
        level = params.get("target_cefr_level", "the target")
        label = subject.display_name or subject.kind.lower()
        if self.gap_type_for(subject, clause, case) == "BELOW_ENTITLEMENT":
            booked = sum((b.magnitude or 0) for b in self._bookings_for(case, subject))
            return (
                f"Top up language training for {label}: booked {booked:.0f}h, "
                f"policy promises {hours}h to {label}."
            )
        return (
            f"Book {hours}h {level} language training for {label} "
            f"(clause {clause.policy_clause_id})."
        )

    def _bookings_for(self, case: Case, subject: Subject) -> "tuple[Artefact, ...]":
        return case.find_artefacts(
            kind=self.ARTEFACT_KIND, family_member_id=subject.family_member_id
        )


register(LanguageTrainingEvidence())
