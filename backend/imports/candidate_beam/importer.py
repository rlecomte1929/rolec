"""Import approved beam candidates into the EXISTING otto_staging flow.

Reuse, not a parallel pipeline: this module converts an approved `candidate_beam_items`
row into the `FactRow` that `backend.imports.otto.executor.stage()` already consumes, and
lets that module do the writing, the counting and the reconcile. A second staging path
would mean a second set of counters to be wrong in a second way, and the otto reconciler
exists because the first one once reported `loaded_count=24` while loading nothing.

WHAT THIS DELIBERATELY WILL NOT DO
----------------------------------

**It never promotes.** `promote()` writes `public.requirement_items` — customer-facing.
Beam output is unreviewed model text, so it stops at staging in `needs_review`, and a
human moves it on through the /admin approval gate that already exists. The whole safety
argument for the beam is that its output cannot become customer-facing without a person.

**It never lets beam text reach `auto_accepted`.** `parsers.grade()` awards that tier on
an official publisher plus a quotable line of evidence. A beam `source` is the model's
CLAIM, stored verbatim and unverified — and a claimed source that happens to name
`skatteetaten.no` would otherwise score exactly like a checked citation. So every
beam-origin row is pinned to `needs_review` with the reason recorded. An invented source
survives review by looking already-done; this is the control that stops that.

**It never invents a source to get a row through.** Around 10 of the 35 candidates in the
validated run carry no source at all. `FactRow` requires one, so those cannot be staged —
by design. They stay `approved` in the beam queue as the research worklist the schema
comment calls them, and the caller is told which ones and why.

**It never guesses a pillar it cannot ground.** Seven of the beam's thirteen categories map
onto a production pillar with evidence; six do not, and for those a human selects. Silent
bucketing would put customs paperwork under RESIDENCE and nobody would ever see it happen.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..otto.parsers import (
    CONFIDENCE_SCORES,
    TIER_REVIEW,
    FactRow,
    classify_source,
)

log = logging.getLogger(__name__)

__all__ = [
    "CANONICAL_PILLARS",
    "PILLAR_BY_CATEGORY",
    "ImportPlan",
    "ImportSkip",
    "suggest_pillar",
    "plan_import",
    "to_fact_row",
    "topic_key_for",
]

#: The platform's production pillar vocabulary — measured, not invented:
#: `SELECT pillar, count(*) FROM requirement_items GROUP BY pillar` on 2026-08-19.
#: Canonical for the import selector; the beam's own `category` stays on the candidate
#: verbatim as the audit trail of what the model actually said.
CANONICAL_PILLARS: Tuple[str, ...] = (
    "RESIDENCE",
    "IDENTITY",
    "EMPLOYMENT",
    "HOUSING",
    "SOCIAL_SECURITY",
    "TIMELINE",
    "HEALTHCARE",
)

#: Beam category -> pillar, ONLY where a production row already makes the call. Each entry
#: below is grounded in an existing `requirement_items` row, not in intuition:
#:
#:   tax             -> EMPLOYMENT   "Tax deduction card (skattekort) before first salary"
#:   payroll         -> EMPLOYMENT   same family — payroll obligations ride the employment pillar
#:   health          -> HEALTHCARE   "French health cover (CPAM affiliation)"
#:   housing         -> HOUSING      "Long-term housing contract"
#:   registration    -> RESIDENCE    "Residence registration (folkeregister)"
#:   immigration     -> RESIDENCE    residence permits are the residence pillar
#:   social_security -> SOCIAL_SECURITY  "National Insurance registration (folketrygden)"
#:
#: Absent on purpose: customs, pets, driving, banking, family, other. None of the seven
#: pillars covers them, and there is no production row to copy. A human picks, or the
#: candidate is not imported — see `suggest_pillar`.
PILLAR_BY_CATEGORY: Dict[str, str] = {
    "tax": "EMPLOYMENT",
    "payroll": "EMPLOYMENT",
    "health": "HEALTHCARE",
    "housing": "HOUSING",
    "registration": "RESIDENCE",
    "immigration": "RESIDENCE",
    "social_security": "SOCIAL_SECURITY",
}


def suggest_pillar(category: Optional[str]) -> Optional[str]:
    """The grounded pillar for a beam category, or None when a human must choose.

    None is a real answer, not a failure: six of the thirteen categories have no honest
    pillar, and defaulting them would hide that decision inside an import.
    """
    if not category:
        return None
    return PILLAR_BY_CATEGORY.get(str(category).strip().lower())


def topic_key_for(title: str) -> str:
    """`Tax Exit from France` -> `tax_exit_from_france`.

    The otto entity key. Derived from the title because that is the only stable identifier
    a beam candidate has; `candidate_uid` is per-run and would fragment the same obligation
    across re-runs into separate staging entities.
    """
    cleaned = "".join(ch.lower() if (ch.isalnum() or ch.isspace()) else " " for ch in (title or ""))
    return "_".join(cleaned.split()) or "untitled"


@dataclass
class ImportSkip:
    """One candidate that will NOT be staged, and the reason a reviewer can act on."""

    candidate_uid: str
    title: str
    reason: str


@dataclass
class ImportPlan:
    """What an import would do. Built before anything is written, so it can be shown."""

    rows: List[FactRow] = field(default_factory=list)
    skipped: List[ImportSkip] = field(default_factory=list)
    #: candidate_uid -> the pillar chosen for it, for the audit stamp after staging.
    pillar_by_uid: Dict[str, str] = field(default_factory=dict)

    @property
    def importable(self) -> int:
        return len(self.rows)

    def skips_by_reason(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for skip in self.skipped:
            key = skip.reason.split(":", 1)[0]
            counts[key] = counts.get(key, 0) + 1
        return counts


def to_fact_row(
    candidate: Dict[str, Any],
    *,
    country: str,
    batch_id: str,
    pillar: str,
) -> FactRow:
    """Convert ONE approved candidate into a stageable FactRow.

    Pinned to `needs_review` regardless of how official the claimed source looks — see the
    module docstring. `evidence_quote` is deliberately left empty: the beam has no quoted
    line, and synthesising one from the model's own prose would manufacture the very
    evidence the tier is supposed to measure.
    """
    title = str(candidate.get("title") or "").strip()
    source = (candidate.get("source") or "").strip()
    if not title:
        raise ValueError("candidate has no title")
    if not source:
        raise ValueError("candidate has no source")
    if pillar not in CANONICAL_PILLARS:
        raise ValueError(f"pillar {pillar!r} is not one of {list(CANONICAL_PILLARS)}")

    body = "\n\n".join(
        part
        for part in (
            str(candidate.get("official_guidance") or "").strip(),
            str(candidate.get("actual_reality") or "").strip(),
            str(candidate.get("action_required") or "").strip(),
        )
        if part
    )

    row = FactRow(
        destination_country=country,
        entity_topic_key=topic_key_for(title),
        fact_key=pillar.lower(),
        fact_text=body,
        source_url=source,
        batch_id=batch_id,
        entity_title=title,
        fact_type="other",
        applies_to={
            "pillar": pillar,
            # The model's own word, kept verbatim beside the canonical pillar. The pillar
            # is what the platform selects on; this is what the model actually said, and
            # losing it would erase the only record of how the mapping was made.
            "beam_category": candidate.get("category"),
            "beam_candidate_uid": candidate.get("candidate_uid"),
            "beam_pass_frequency": candidate.get("pass_frequency"),
            "beam_confidence_band": candidate.get("confidence_band"),
        },
        evidence_quote=None,
        confidence="medium",
    )

    row.source_class = classify_source(row.source_url)
    row.confidence_score = min(
        CONFIDENCE_SCORES["medium"], CONFIDENCE_SCORES.get(row.confidence, 0.6)
    )
    # The control. grade() would award auto_accepted to an official-looking host; a beam
    # source is an unverified claim, so the tier is pinned and the reason is recorded.
    row.accuracy_tier = TIER_REVIEW
    row.downgrades.append(
        "beam-origin: source is the model's unverified claim, not a checked citation — "
        "pinned to needs_review"
    )
    if row.source_class != "official":
        row.downgrades.append(f"claimed publisher is {row.source_class}")
    if candidate.get("flagged"):
        row.downgrades.append("flagged in beam review")
    return row


def plan_import(
    candidates: Sequence[Dict[str, Any]],
    *,
    country: str,
    batch_id: str,
    pillar_overrides: Optional[Dict[str, str]] = None,
) -> ImportPlan:
    """Decide what would be staged, without writing anything.

    Only `approved` candidates are eligible: the beam review queue is the human gate, and
    importing `pending_review` rows would route around it. Everything skipped is reported
    with a reason rather than dropped, because a partial import that looks complete is the
    failure this repo's importers were built to stop.
    """
    overrides = {k: v for k, v in (pillar_overrides or {}).items()}
    plan = ImportPlan()

    for candidate in candidates:
        uid = str(candidate.get("candidate_uid") or candidate.get("id") or "")
        title = str(candidate.get("title") or "").strip() or "(untitled)"
        status = str(candidate.get("status") or "").strip()

        if status != "approved":
            plan.skipped.append(ImportSkip(uid, title, f"not approved: status={status or 'unset'}"))
            continue

        if not (candidate.get("source") or "").strip():
            plan.skipped.append(
                ImportSkip(uid, title, "no source: research worklist, not importable")
            )
            continue

        pillar = overrides.get(uid) or suggest_pillar(candidate.get("category"))
        if not pillar:
            plan.skipped.append(
                ImportSkip(
                    uid,
                    title,
                    f"pillar unresolved: category {candidate.get('category')!r} has no grounded "
                    f"pillar — select one of {list(CANONICAL_PILLARS)}",
                )
            )
            continue
        if pillar not in CANONICAL_PILLARS:
            plan.skipped.append(ImportSkip(uid, title, f"pillar invalid: {pillar!r}"))
            continue

        try:
            plan.rows.append(to_fact_row(candidate, country=country, batch_id=batch_id, pillar=pillar))
        except ValueError as exc:
            plan.skipped.append(ImportSkip(uid, title, f"unusable: {exc}"))
            continue
        plan.pillar_by_uid[uid] = pillar

    return plan


def audit_stamp(
    *,
    country: str,
    pillar: str,
    batch_id: str,
    imported_by: str,
) -> Dict[str, Any]:
    """The `candidate_beam_items` audit columns for a staged candidate.

    The table's CHECK refuses `status='imported'` unless import_country,
    import_requirement_type, imported_ref and imported_at are all present — so this returns
    all four together rather than letting a caller assemble a partial stamp that the
    database then rejects mid-batch.
    """
    return {
        "status": "imported",
        "import_country": country,
        "import_requirement_type": pillar,
        "imported_ref": batch_id,
        "imported_at": datetime.now(timezone.utc),
        "imported_by": imported_by,
    }
