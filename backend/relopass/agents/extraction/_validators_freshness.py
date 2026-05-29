"""Freshness validator (C2-02a, standalone).

Pure-stdlib helper for document freshness checks. Lands as a standalone
module so it can be authored and unit-tested INDEPENDENTLY of the C1-05a
Extraction Agent runtime.

When C1-05a merges to main, the integration step is one line: inline
`freshness_finding` and `Finding` into `_common.py` alongside the existing
`call_llm_with_retry` and `make_field` helpers, and delete this file. The
fixture-based tests in `backend/tests/test_validators_freshness.py` will
move with it.

Why this matters:
    Criminal-record / tax-cert / housing-lease documents have a freshness
    contract — receiving authorities (BAMF, UDI, Préfectures) reject
    documents older than a corridor-specific cutoff. ReloPass enforces a
    unified 180-day default (the most generous of the three) at the
    extraction layer and lets corridor agents apply tighter thresholds
    downstream (e.g. UDI Skilled-Worker = 90 days).

Architecture Report references:
    §3.3 — personal-document validation rules table.
    §3.6 — contradiction / finding emission shape.
    §15 Cohort 2 task C2-02 — the parent task.

Public surface:
    Finding              — minimal severity + code + message dataclass.
    FindingSeverity      — Literal type alias for INFO / WARN / ERROR.
    freshness_finding()  — the predicate.
    early_warning_finding() — soft predicate emitted at extraction time.

Provenance: originally written on branch feat/c1-11de-pdf-viewer-bbox-overlay
during the C2-02a session (2026-05-29). Re-shipped here on
feat/intake-city-prefill-code during the C2-02b session because branch
switching between Cowork sessions meant the original file isn't reachable
from this worktree. Content is byte-identical so a future rebase merges
cleanly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Final, Literal, Optional


FindingSeverity = Literal["INFO", "WARN", "ERROR"]


#: Default freshness threshold in days. Chosen as the most-generous of the
#: three Cohort 2 receiving-authority thresholds (FR/DE/NO criminal records,
#: where 180 days covers the typical 3-month and 6-month windows). Corridor
#: agents apply tighter thresholds (e.g. UDI 90 days) at their own layer.
DEFAULT_MAX_AGE_DAYS: Final[int] = 180

#: Early-warning threshold (the prompt emits FRESHNESS_AT_RISK before the
#: runtime emits the hard CRIMINAL_RECORD_STALE so the HR operator gets
#: lead time on the renewal request).
DEFAULT_EARLY_WARNING_DAYS: Final[int] = 150


@dataclass(frozen=True, slots=True)
class Finding:
    """A single extraction-time observation about a document.

    Findings are NOT validation failures by themselves; they're signals the
    runtime emits alongside the structured extraction so the HR operator
    can triage. The downstream Resolution UI (C1-12) renders them.

    Attributes:
        severity: INFO (purely informational), WARN (needs human review),
            ERROR (extraction-time hard failure).
        code: Controlled-vocabulary identifier. See the per-prompt
            "Findings vocabulary" section for the canonical enum.
        message: Human-readable explanation. Surfaced in the Resolution UI.
        bbox: Optional 0-1000 normalised bounding box pointing at the
            source text that triggered the finding. None when the finding
            is derived (e.g. computed from a date, not a span of text).
    """

    severity: FindingSeverity
    code: str
    message: str
    bbox: Optional[tuple[int, int, int, int]] = field(default=None)


def freshness_finding(
    issue_date: date,
    *,
    reference_date: date,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    code: str = "CRIMINAL_RECORD_STALE",
) -> Optional[Finding]:
    """Return a WARN-severity Finding if ``issue_date`` is older than the
    freshness threshold, else None.

    The validator is symmetric (positive `(reference_date - issue_date).days`
    means the document is in the past). A document issued AFTER the
    reference date — which shouldn't happen in practice but might from a
    typo'd `issue_date` — never triggers staleness; it's caught by the
    upstream date sanity check (not this validator's responsibility).

    Args:
        issue_date: The date the document was issued (extracted from the
            document body, typically the "Délivré le" / "Ausgestellt am" /
            "Utstedt" field).
        reference_date: The date to compare against. Almost always
            ``case.created_at.date()`` so freshness is measured at the
            moment the document was uploaded to the case, not at every
            re-evaluation. Pass ``date.today()`` for simple call sites.
        max_age_days: Threshold in days. Default 180 (engine-wide). Pass
            90 from the NO Skilled-Worker corridor agent, 180 from the
            DE Blue Card corridor agent.
        code: Override the finding code if you want a corridor-specific
            label (e.g. "TAX_CERT_STALE" when re-using this helper from
            the C2-02b agent).

    Returns:
        Finding with severity="WARN" if stale, else None.

    Examples:
        >>> from datetime import date
        >>> # Fresh — issued today
        >>> freshness_finding(date(2026, 5, 29), reference_date=date(2026, 5, 29)) is None
        True
        >>> # Stale — issued 200 days ago
        >>> f = freshness_finding(date(2025, 11, 10), reference_date=date(2026, 5, 29))
        >>> f.severity, f.code
        ('WARN', 'CRIMINAL_RECORD_STALE')
        >>> # Boundary — exactly 180 days ago is NOT stale (the threshold is exclusive)
        >>> freshness_finding(date(2025, 11, 30), reference_date=date(2026, 5, 29)) is None
        True
        >>> # Corridor-specific tighter threshold
        >>> freshness_finding(
        ...     date(2026, 1, 1), reference_date=date(2026, 5, 29),
        ...     max_age_days=90, code="UDI_SKILLED_WORKER_STALE",
        ... ).code
        'UDI_SKILLED_WORKER_STALE'
    """
    age_days = (reference_date - issue_date).days
    if age_days <= max_age_days:
        return None
    return Finding(
        severity="WARN",
        code=code,
        message=(
            f"Document issued {age_days} days ago, exceeds {max_age_days}-day "
            f"freshness threshold. Renew before submitting to the receiving authority."
        ),
    )


def early_warning_finding(
    issue_date: date,
    *,
    reference_date: date,
    early_warning_days: int = DEFAULT_EARLY_WARNING_DAYS,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    code: str = "FRESHNESS_AT_RISK",
) -> Optional[Finding]:
    """Return an early-warning Finding when the document is approaching
    staleness but not yet stale.

    Use this in the extraction-prompt findings vocabulary (the prompts
    emit FRESHNESS_AT_RISK at extraction time so the case picks up the
    soft signal before the hard threshold fires). Returns None if the
    document is either fully fresh or already stale (the runtime emits
    the hard `freshness_finding` in the latter case).

    Args:
        issue_date: As above.
        reference_date: As above.
        early_warning_days: Lower bound of the warning window. Default 150.
        max_age_days: Upper bound; documents older than this trigger the
            hard `freshness_finding` instead. Default 180.
        code: Defaults to ``FRESHNESS_AT_RISK`` to match the prompt
            findings vocabulary.

    Returns:
        Finding with severity="WARN" if in the early-warning window, else None.
    """
    age_days = (reference_date - issue_date).days
    if age_days <= early_warning_days or age_days > max_age_days:
        return None
    return Finding(
        severity="WARN",
        code=code,
        message=(
            f"Document is {age_days} days old (within {early_warning_days}-{max_age_days} day "
            f"window). Consider renewing proactively."
        ),
    )
