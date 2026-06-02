"""Lightweight projection types for the policy-evidence detector.

These dataclasses are NOT the ORM models. They're stdlib-pure projections
that the eventual Supabase adapter materialises from ``rce.cases``,
``rce.family_members``, ``rce.documents``, ``rce.policy_clauses``, and
related tables. This separation keeps the detector trivially testable
without a database or pydantic.

The adapter lives in ``backend/app/services/policy_gap_detector_adapter.py``
(out of scope for C2-06; ship in a follow-up).

All dataclasses are frozen + slotted for cheap equality + hashability +
defensiveness against accidental mutation in the detector.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final, Literal, Mapping, Optional, Sequence
from uuid import UUID

RelationshipType = Literal["SPOUSE", "CHILD", "DEPENDENT_PARENT"]
SubjectKind = Literal["EMPLOYEE", "SPOUSE", "CHILD", "DEPENDENT_PARENT", "CASE"]
GapType = Literal["MISSING_BENEFIT_DELIVERY", "MISSING_DOCUMENT", "BELOW_ENTITLEMENT"]

# ``slots=True`` only exists on the dataclass decorator from Python 3.10.
# Keep the slotted behaviour where available; degrade gracefully on 3.9.
_DC_KW: dict[str, bool] = {"frozen": True}
if sys.version_info >= (3, 10):
    _DC_KW["slots"] = True


@dataclass(**_DC_KW)
class FamilyMember:
    """Projection of a single rce.family_members row.

    Carries the minimum the evidence checks need: who is this person on
    the case, and what's their canonical identity. Display name lives on
    the canonical entity, not here.
    """

    family_member_id: UUID
    relationship_type: RelationshipType
    canonical_entity_id: UUID
    display_name: Optional[str] = None


@dataclass(**_DC_KW)
class PolicyClause:
    """Projection of a single rce.policy_clauses row.

    ``parameters_json`` is the per-clause-type parameters object — the
    shape varies by clause_type per Architecture Report §6.1. The
    evidence check for each clause_type knows how to read it.

    ``bbox_citation`` is the citation primitive — points back to the
    source policy PDF page/region so the HR Dashboard can render the
    "why am I seeing this?" link.
    """

    policy_clause_id: UUID
    hr_policy_id: UUID
    clause_type: str
    parameters_json: Mapping[str, Any] = field(default_factory=dict)
    bbox_citation: Optional[Mapping[str, Any]] = None


@dataclass(**_DC_KW)
class Artefact:
    """A piece of case-attached evidence consumed by evidence checks.

    Artefacts are heterogeneous — a language_training_booking, a
    housing_lease document upload, an immigration permit application
    submission, etc. The ``kind`` discriminator + ``payload`` JSONB shape
    is the contract each evidence-check module reads against. The
    ``subject`` link tells us WHO the artefact pertains to (when None,
    the artefact is case-scope).

    Quantity (``magnitude`` + ``unit``) is optional, used by
    BELOW_ENTITLEMENT comparisons — e.g. a language_training_booking
    with magnitude=20, unit='hours' vs a policy minimum of 60.
    """

    artefact_id: UUID
    kind: str
    subject_kind: SubjectKind
    family_member_id: Optional[UUID] = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    magnitude: Optional[float] = None
    unit: Optional[str] = None
    delivered_at: Optional[datetime] = None


@dataclass(**_DC_KW)
class Case:
    """Projection of a single rce.cases row plus its related collections.

    The detector treats this as a snapshot — no laziness, no DB calls
    inside the check. The adapter is responsible for hydrating the
    relevant family_members + artefacts before passing it in.
    """

    case_id: UUID
    employer_id: UUID
    primary_employee_id: UUID
    primary_employee_canonical_id: UUID
    primary_employee_display_name: Optional[str] = None
    target_arrival_date: Optional[str] = None
    family_members: Sequence[FamilyMember] = field(default_factory=tuple)
    artefacts: Sequence[Artefact] = field(default_factory=tuple)

    def find_artefacts(
        self,
        kind: Optional[str] = None,
        subject_kind: Optional[SubjectKind] = None,
        family_member_id: Optional[UUID] = None,
    ) -> "tuple[Artefact, ...]":
        """Return all artefacts on the case matching the predicate.

        Pure filter, no I/O. Used inside evidence-check ``evidence_for_subject``
        implementations.
        """
        return tuple(
            a
            for a in self.artefacts
            if (kind is None or a.kind == kind)
            and (subject_kind is None or a.subject_kind == subject_kind)
            and (family_member_id is None or a.family_member_id == family_member_id)
        )

    def family_by_relationship(
        self, relationship: RelationshipType
    ) -> "tuple[FamilyMember, ...]":
        """Return all family members of the given relationship type."""
        return tuple(
            fm for fm in self.family_members if fm.relationship_type == relationship
        )


@dataclass(**_DC_KW)
class Subject:
    """Who a clause / gap is about.

    ``EMPLOYEE`` uses the case.primary_employee_id, family_member_id is None.
    ``SPOUSE`` / ``CHILD`` / ``DEPENDENT_PARENT`` carry the family_member_id.
    ``CASE`` is the case as a whole (e.g. RELOCATION_ALLOWANCE).
    """

    kind: SubjectKind
    family_member_id: Optional[UUID] = None
    canonical_entity_id: Optional[UUID] = None
    display_name: Optional[str] = None

    def dedup_key(self) -> str:
        """Stable string key for the gap UNIQUE constraint mirror.

        Mirrors the SQL ``UNIQUE (case_id, policy_clause_id, gap_type,
        family_member_id)`` semantics — for case-scope clauses
        (family_member_id IS NULL), the SQL uses a sentinel UUID; here
        we use the literal string "CASE" for the same purpose.
        """
        if self.family_member_id is not None:
            return str(self.family_member_id)
        return "CASE"


@dataclass(**_DC_KW)
class Gap:
    """A single detected entitlement gap, ready for INSERT into rce.policy_gaps.

    The detector returns these as a tuple; the adapter persists them.
    Equality is structural, so deduping inside the detector is cheap.
    """

    case_id: UUID
    policy_clause_id: UUID
    clause_type: str
    subject: Subject
    gap_type: GapType
    suggested_action: str
    evidence_payload: Optional[Mapping[str, Any]] = None
    citation: Optional[Mapping[str, Any]] = None

    def dedup_key(self) -> tuple:
        """Hashable dedup key matching the SQL UNIQUE constraint."""
        return (
            self.case_id,
            self.policy_clause_id,
            self.gap_type,
            self.subject.dedup_key(),
        )


CASE_SUBJECT_SENTINEL: Final[str] = "CASE"
