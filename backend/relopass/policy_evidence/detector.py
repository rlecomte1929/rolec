"""Policy-gap detector orchestrator (C2-06).

The single public entry point :func:`detect_gaps` iterates the applicable
clauses on a case, dispatches each to the registered evidence check, and
returns a deduplicated tuple of :class:`Gap` ready for INSERT into
``rce.policy_gaps``.

Pure function — no I/O. The Supabase persistence adapter (next session)
wraps this and:

    1. Reads existing open gaps for the case.
    2. Calls detect_gaps with a hydrated Case + applicable clauses.
    3. Diffs detected vs existing:
         * In both       → no-op
         * Detected only → INSERT
         * Existing only → UPDATE SET cleared_at = now(), evidence_payload = ...
    4. Returns the diff for the caller's audit trail.

The detector itself is async-safe in the sense that "running twice on the
same inputs produces the same output" — there's no internal state. Race
conditions during INSERT are handled at the SQL layer via the UNIQUE
constraint on (case_id, policy_clause_id, gap_type, family_member_id).
"""

from __future__ import annotations

from typing import Iterable

from ._models import Case, Gap, PolicyClause
from .registry import get as get_check


def detect_gaps(
    case: Case, applicable_clauses: Iterable[PolicyClause]
) -> "tuple[Gap, ...]":
    """Detect entitlement gaps between ``case`` and ``applicable_clauses``.

    For each clause:
      * Look up the registered EvidenceCheck for ``clause.clause_type``.
        If none is registered, skip silently (deferred clause types
        don't emit gaps — they're tracked via a separate metric).
      * Enumerate the subjects the clause applies to. If empty, skip.
      * For each subject, call ``evidence_for_subject``. If None,
        construct a Gap with the appropriate gap_type + suggested_action
        + clause citation.

    Returns:
        Deduplicated tuple of Gap. Dedup is by the same key as the SQL
        UNIQUE constraint: (case_id, policy_clause_id, gap_type,
        subject_dedup_key).

    Performance:
        O(n_clauses × n_subjects_per_clause). For Cohort 2 typical loads
        (≤20 clauses × ≤4 subjects = ≤80 checks per case), the detector
        runs in <5ms on a modern laptop. The 200ms validation criterion
        accommodates the adapter's DB round-trips, not the detector
        itself.
    """
    seen = set()
    gaps = []
    for clause in applicable_clauses:
        check = get_check(clause.clause_type)
        if check is None:
            continue
        subjects = check.applicable_subjects(clause, case)
        if not subjects:
            continue
        for subject in subjects:
            evidence = check.evidence_for_subject(subject, clause, case)
            if evidence is not None:
                continue
            gap = Gap(
                case_id=case.case_id,
                policy_clause_id=clause.policy_clause_id,
                clause_type=clause.clause_type,
                subject=subject,
                gap_type=check.gap_type_for(subject, clause, case),
                suggested_action=check.suggested_action_for(subject, clause, case),
                evidence_payload=None,
                citation=clause.bbox_citation,
            )
            key = gap.dedup_key()
            if key in seen:
                continue
            seen.add(key)
            gaps.append(gap)
    return tuple(gaps)
