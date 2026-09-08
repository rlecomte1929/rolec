"""EvidenceCheck base class (C2-06).

Every clause type registers exactly one EvidenceCheck. The contract is
small on purpose: enumerate the subjects the clause applies to, and for
each subject, decide whether evidence of delivery exists on the case.

The base class is abstract; concrete subclasses live in sibling modules
(``language_training.py``, ``housing_benefit.py``, ``immigration_support.py``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Mapping, Optional, Sequence

from ._models import Case, GapType, PolicyClause, Subject


class EvidenceCheck(ABC):
    """Contract for a per-clause-type evidence check.

    Subclasses declare ``clause_type`` as a class attribute (matches the
    ``rce.policy_clauses.clause_type`` value) and implement two methods:

    * :meth:`applicable_subjects` — given a clause + case, enumerate WHO
      this clause applies to. Returns a tuple of :class:`Subject`.
    * :meth:`evidence_for_subject` — given a subject + clause + case,
      either return an evidence dict (delivery confirmed) or None
      (gap detected).

    The detector handles the SQL persistence shape, dedup, and citation
    propagation. Subclasses focus purely on the domain question
    "is this benefit delivered for this person on this case?".
    """

    clause_type: ClassVar[str] = ""
    suggested_action_template: ClassVar[Optional[str]] = None
    default_gap_type: ClassVar[GapType] = "MISSING_BENEFIT_DELIVERY"

    @abstractmethod
    def applicable_subjects(
        self, clause: PolicyClause, case: Case
    ) -> Sequence[Subject]:
        """Return the subjects on ``case`` this ``clause`` applies to.

        An empty return means "this clause is not applicable to anyone on
        this case" — the detector skips it without emitting gaps.
        """

    @abstractmethod
    def evidence_for_subject(
        self, subject: Subject, clause: PolicyClause, case: Case
    ) -> Optional[Mapping[str, Any]]:
        """Return the evidence payload (delivery confirmed) or None (gap).

        The evidence payload, when non-None, is stored on the cleared gap
        row's ``evidence_payload`` JSONB column for audit. Keep it small
        and deterministic.
        """

    def suggested_action_for(
        self, subject: Subject, clause: PolicyClause, case: Case
    ) -> str:
        """Return the human-readable suggested-action hint for a gap.

        Default falls back to ``suggested_action_template`` (formatted
        with subject + clause if it's a template string), else a generic
        message.
        """
        if self.suggested_action_template:
            try:
                return self.suggested_action_template.format(
                    subject=subject, clause=clause, case=case
                )
            except (KeyError, IndexError):
                pass
        return (
            f"Policy clause {clause.policy_clause_id} ({clause.clause_type}) "
            f"promises a benefit for {_subject_label(subject)} that has no "
            f"delivery evidence."
        )

    def gap_type_for(
        self, subject: Subject, clause: PolicyClause, case: Case
    ) -> GapType:
        """Return the gap_type for this (subject, clause, case) triple.

        Default returns ``default_gap_type``. Override if a check can
        produce multiple gap types (e.g. LANGUAGE_TRAINING emits
        MISSING_BENEFIT_DELIVERY when no booking exists at all but
        BELOW_ENTITLEMENT when a booking exists with insufficient hours).
        """
        return self.default_gap_type


def _subject_label(subject: Subject) -> str:
    """Human-readable subject label for suggested-action hints."""
    if subject.display_name:
        return subject.display_name
    if subject.kind == "EMPLOYEE":
        return "the employee"
    if subject.kind == "CASE":
        return "this case"
    return "the " + subject.kind.lower().replace("_", " ")
