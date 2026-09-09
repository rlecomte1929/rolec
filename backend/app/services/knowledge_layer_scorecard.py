"""Catalog sufficiency for the knowledge-layer QBR — no LLM, no serving side effects.

A corridor is ready to sell/serve as a catalog when approved rows exist, enough of
them carry a resolvable citation, and more than one pillar is represented. The bars
are conservative and named so a QBR can raise them after a measured baseline; they
are not McKinsey client percentages.

Callers resolve citations with ``requirements_builder.citation_dtos`` (employee and
public) or ``_admin_citation_dtos`` (review). This module only scores already-counted
integers so it cannot drift from either resolver.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Optional, Sequence

# Employee dossier pillars. A single-pillar catalog is not a relocation dossier.
REQUIRED_PILLARS = (
    "IDENTITY",
    "RESIDENCE",
    "EMPLOYMENT",
    "HOUSING",
    "HEALTHCARE",
)

MIN_APPROVED = 1
MIN_PILLARS = 2
# Share of *approved* items that must have ≥1 resolvable citation URL.
CITATION_RESOLVE_BAR = 0.5

NOT_READY_EMPTY = (
    "This corridor is not ready. We have no approved, cited requirements to serve. "
    "That is a catalog gap, not a finding that nothing is required."
)
NOT_READY_CITATIONS = (
    "This corridor is not ready: too few approved requirements carry a resolvable source. "
    "Open the cited URL before treating a line as a fact."
)
NOT_READY_PILLARS = (
    "This corridor is not ready: approved items do not yet cover more than one requirement pillar."
)


@dataclass(frozen=True)
class KnowledgeScorecard:
    approved_count: int
    pending_count: int
    rejected_count: int
    citation_resolved_approved: int
    citation_resolve_pct: float
    pillars_present: tuple[str, ...]
    last_human_review_at: Optional[datetime]
    catalog_ready: bool
    not_ready_reason: Optional[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "approvedCount": self.approved_count,
            "pendingCount": self.pending_count,
            "rejectedCount": self.rejected_count,
            "citationResolvedApproved": self.citation_resolved_approved,
            "citationResolvePct": self.citation_resolve_pct,
            "pillarsPresent": list(self.pillars_present),
            "lastHumanReviewAt": (
                self.last_human_review_at.isoformat() if self.last_human_review_at else None
            ),
            "catalogReady": self.catalog_ready,
            "notReadyReason": self.not_ready_reason,
        }


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(100.0 * numerator / denominator, 1)


def score_catalog(
    *,
    approved_count: int,
    pending_count: int,
    rejected_count: int = 0,
    citation_resolved_approved: int,
    pillars: Iterable[str],
    last_human_review_at: Optional[datetime] = None,
) -> KnowledgeScorecard:
    pillars_present = tuple(sorted({p for p in pillars if p}))
    resolve_pct = _pct(citation_resolved_approved, approved_count)
    reason: Optional[str] = None
    ready = True
    if approved_count < MIN_APPROVED:
        ready = False
        reason = NOT_READY_EMPTY
    elif approved_count > 0 and (citation_resolved_approved / approved_count) < CITATION_RESOLVE_BAR:
        ready = False
        reason = NOT_READY_CITATIONS
    elif len(pillars_present) < MIN_PILLARS:
        ready = False
        reason = NOT_READY_PILLARS

    return KnowledgeScorecard(
        approved_count=approved_count,
        pending_count=pending_count,
        rejected_count=rejected_count,
        citation_resolved_approved=citation_resolved_approved,
        citation_resolve_pct=resolve_pct,
        pillars_present=pillars_present,
        last_human_review_at=last_human_review_at,
        catalog_ready=ready,
        not_ready_reason=reason,
    )


def parse_citations_json(raw: Any) -> Sequence[Any]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return raw
    if isinstance(raw, str):
        if not raw.strip():
            return []
        import json

        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def count_resolved_citations(citations: Any, source_map: dict) -> int:
    """How many DTOs ``citation_dtos`` would serve for this row (employee/public)."""
    from .requirements_builder import citation_dtos

    return len(citation_dtos(parse_citations_json(citations), source_map))


def score_requirement_rows(rows: Sequence[Any], source_map: dict) -> KnowledgeScorecard:
    """Score ORM (or namespace) requirement_items using the employee citation resolver."""
    approved = pending = rejected = resolved_approved = 0
    pillars: list[str] = []
    last_review: Optional[datetime] = None
    for row in rows:
        status = (getattr(row, "review_status", None) or "approved").strip().lower()
        if status == "pending":
            pending += 1
        elif status == "rejected":
            rejected += 1
        else:
            approved += 1
            pillar = getattr(row, "pillar", None) or ""
            if pillar:
                pillars.append(pillar)
            citations = getattr(row, "citations_json", None)
            if count_resolved_citations(citations, source_map) > 0:
                resolved_approved += 1
        reviewed_at = getattr(row, "reviewed_at", None)
        if reviewed_at is not None and (last_review is None or reviewed_at > last_review):
            last_review = reviewed_at
    return score_catalog(
        approved_count=approved,
        pending_count=pending,
        rejected_count=rejected,
        citation_resolved_approved=resolved_approved,
        pillars=pillars,
        last_human_review_at=last_review,
    )
