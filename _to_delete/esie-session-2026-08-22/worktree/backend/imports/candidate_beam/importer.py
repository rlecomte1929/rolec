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

from sqlalchemy import text

from ..otto.executor import stage
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

    Pinned to `needs_review` regardless of how official the source looks — see the module
    docstring — and that holds for a human-researched source too. A person finding the right
    government page is better provenance than a model claim, and it is still not a checked
    citation; lifting the tier here would undo the argument the whole feature rests on.

    Two sources are possible and they are NOT interchangeable in the record:
    `source` is the model's verbatim claim, `researched_source_url` is a human's finding for a
    candidate the beam could not cite. The model's claim wins when both exist — it is what the
    row was generated from — and whichever is used is named in `downgrades`, so a reader of
    the staged row can tell them apart without joining back to the beam tables.

    `evidence_quote` stays empty for a model-claimed source: the beam has no quoted line, and
    synthesising one from its own prose would manufacture the very evidence the tier measures.
    A researched source may carry one, because a person actually read the page.
    """
    title = str(candidate.get("title") or "").strip()
    claimed = (candidate.get("source") or "").strip()
    researched = (candidate.get("researched_source_url") or "").strip()
    source = claimed or researched
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
        # Only a human-researched source can carry a quote; see the docstring.
        evidence_quote=(
            (str(candidate.get("researched_evidence_quote") or "").strip() or None)
            if not claimed
            else None
        ),
        confidence="medium",
    )

    row.source_class = classify_source(row.source_url)
    row.confidence_score = min(
        CONFIDENCE_SCORES["medium"], CONFIDENCE_SCORES.get(row.confidence, 0.6)
    )
    # The control. grade() would award auto_accepted to an official-looking host; a beam
    # source is an unverified claim, so the tier is pinned and the reason is recorded.
    row.accuracy_tier = TIER_REVIEW
    if claimed:
        row.downgrades.append(
            "beam-origin: source is the model's unverified claim, not a checked citation — "
            "pinned to needs_review"
        )
    else:
        row.downgrades.append(
            "beam-origin: source is human-researched, not model-claimed — still unverified, "
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

        if not (
            (candidate.get("source") or "").strip()
            or (candidate.get("researched_source_url") or "").strip()
        ):
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


# ---------------------------------------------------------------------------
# Execution — the only path that writes, and the read-only check that it held
# ---------------------------------------------------------------------------


@dataclass
class ImportConflict:
    """A re-import that would change where an already-imported candidate landed.

    Refused rather than applied. The first import created a staging row under a specific
    country and pillar; silently re-pointing the beam item at a different one would leave
    the original row orphaned in `otto_staging` with nothing referencing it, and
    `verify_import` would then confirm a row that no longer matches what a human approved.
    """

    candidate_uid: str
    title: str
    field: str
    already: str
    requested: str

    @property
    def reason(self) -> str:
        return (
            f"already imported with {self.field}={self.already!r}; "
            f"refusing to change it to {self.requested!r}"
        )


@dataclass
class ImportResult:
    batch_id: str
    dry_run: bool
    staged: int = 0
    already_present: int = 0
    stamped: int = 0
    skipped: List[ImportSkip] = field(default_factory=list)
    conflicts: List[ImportConflict] = field(default_factory=list)
    rejections: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.conflicts


_STAMP_SQL = text(
    """
    UPDATE public.candidate_beam_items
       SET status = :status,
           import_country = :import_country,
           import_requirement_type = :import_requirement_type,
           imported_ref = :imported_ref,
           imported_at = :imported_at,
           imported_by = :imported_by,
           updated_at = now()
     WHERE run_id = :run_id AND candidate_uid = :candidate_uid
    """
)


def _freeze_conflicts(
    candidates: Sequence[Dict[str, Any]],
    *,
    country: str,
    pillar_overrides: Optional[Dict[str, str]],
) -> Tuple[List[ImportConflict], List[Dict[str, Any]], List[ImportSkip]]:
    """Split candidates into (conflicts, still-importable, already-done).

    An item already at `imported` is frozen. Re-importing it unchanged is a no-op rather
    than an error — an operator re-running a partly-failed batch should not have to
    hand-pick the rows that already went through.
    """
    conflicts: List[ImportConflict] = []
    importable: List[Dict[str, Any]] = []
    already: List[ImportSkip] = []
    overrides = pillar_overrides or {}

    for candidate in candidates:
        uid = str(candidate.get("candidate_uid") or candidate.get("id") or "")
        title = str(candidate.get("title") or "").strip() or "(untitled)"
        if str(candidate.get("status") or "") != "imported":
            importable.append(candidate)
            continue

        requested_pillar = overrides.get(uid) or suggest_pillar(candidate.get("category")) or ""
        prior_country = str(candidate.get("import_country") or "")
        prior_pillar = str(candidate.get("import_requirement_type") or "")

        if prior_country and prior_country != country:
            conflicts.append(ImportConflict(uid, title, "country", prior_country, country))
        elif requested_pillar and prior_pillar and prior_pillar != requested_pillar:
            conflicts.append(
                ImportConflict(uid, title, "pillar", prior_pillar, requested_pillar)
            )
        else:
            already.append(ImportSkip(uid, title, "already imported"))

    return conflicts, importable, already


def execute_import(
    conn: Any,
    *,
    run_id: str,
    candidates: Sequence[Dict[str, Any]],
    country: str,
    batch_id: str,
    imported_by: str,
    pillar_overrides: Optional[Dict[str, str]] = None,
    dry_run: bool = True,
) -> ImportResult:
    """Stage approved candidates, then stamp their audit columns.

    Takes a Connection inside a transaction the CALLER owns, exactly as `executor.stage`
    does, so a failure between staging and stamping rolls back both. The alternative —
    staging in one transaction and stamping in another — can leave an item marked
    `imported` whose staging row was rolled back, which is the one state `verify_import`
    cannot distinguish from tampering.

    **Stages; never promotes.** `executor.promote()` writes `public.requirement_items`,
    which is customer-facing. Beam output stops at `otto_staging` with
    `review_status='pending'` and reaches a customer only through /admin/countries.

    A dry run takes the same path and performs the same reads, so its numbers are the
    numbers a real run produces — and it writes nothing, including no audit stamp.
    """
    conflicts, importable, already = _freeze_conflicts(
        candidates, country=country, pillar_overrides=pillar_overrides
    )

    result = ImportResult(batch_id=batch_id, dry_run=dry_run, conflicts=conflicts)
    result.skipped.extend(already)

    # A conflict aborts the batch rather than importing around it: the operator asked for
    # something the freeze forbids, and importing the remainder would half-apply an
    # instruction they would reasonably read as atomic.
    if conflicts:
        return result

    plan = plan_import(
        importable, country=country, batch_id=batch_id, pillar_overrides=pillar_overrides
    )
    result.skipped.extend(plan.skipped)

    if not plan.rows:
        return result

    staged = stage(conn, plan.rows, dry_run=dry_run)
    result.staged = staged.inserted
    result.already_present = staged.already_present
    result.rejections = list(staged.rejections)

    if dry_run:
        return result

    for row in plan.rows:
        uid = (row.applies_to or {}).get("beam_candidate_uid")
        if not uid:
            continue
        stamp = audit_stamp(
            country=country,
            pillar=plan.pillar_by_uid.get(str(uid), row.fact_key.upper()),
            batch_id=batch_id,
            imported_by=imported_by,
        )
        conn.execute(_STAMP_SQL, {"run_id": run_id, "candidate_uid": str(uid), **stamp})
        result.stamped += 1

    return result


@dataclass
class VerifyFinding:
    candidate_uid: str
    title: str
    problem: str
    detail: str


@dataclass
class VerifyReport:
    """Read-only QA of an import. Writes nothing, ever."""

    run_id: str
    checked: int = 0
    intact: int = 0
    findings: List[VerifyFinding] = field(default_factory=list)
    approved_not_imported: int = 0

    @property
    def ok(self) -> bool:
        return not self.findings


_VERIFY_SQL = text(
    """
    SELECT dedupe_key, fact_text, destination_country,
           applies_to ->> 'pillar'              AS pillar,
           applies_to ->> 'beam_candidate_uid'  AS beam_uid
      FROM otto_staging.immigration_fact_candidates
     WHERE dedupe_key = ANY(:keys)
    """
)


def expected_dedupe_key(item: Dict[str, Any]) -> str:
    """The staging key an imported item must have produced.

    Recomputed from the item rather than stored, so the check is independent of the write:
    a verify that read back a key the importer saved would confirm its own arithmetic and
    miss the row being edited underneath it.
    """
    return "|".join(
        [
            str(item.get("import_country") or ""),
            topic_key_for(str(item.get("title") or "")),
            str(item.get("import_requirement_type") or "").lower(),
        ]
    )


def expected_body(item: Dict[str, Any]) -> str:
    return "\n\n".join(
        part
        for part in (
            str(item.get("official_guidance") or "").strip(),
            str(item.get("actual_reality") or "").strip(),
            str(item.get("action_required") or "").strip(),
        )
        if part
    )


def verify_import(
    conn: Any,
    *,
    run_id: str,
    imported_items: Sequence[Dict[str, Any]],
    approved_not_imported: int = 0,
) -> VerifyReport:
    """Confirm every imported candidate still has its staging row, unchanged.

    Three distinct problems, kept distinct because they need different responses: a row
    that VANISHED (someone deleted it), a row whose CONTENT drifted (someone edited the
    text a human approved), and a row filed under a different PILLAR or COUNTRY than the
    stamp records (the import audit trail no longer describes reality).

    Read-only by construction — it issues one SELECT and no writes at all.
    """
    report = VerifyReport(run_id=run_id, approved_not_imported=approved_not_imported)
    if not imported_items:
        return report

    wanted = {expected_dedupe_key(item): item for item in imported_items}
    report.checked = len(imported_items)

    rows = conn.execute(_VERIFY_SQL, {"keys": list(wanted)}).mappings().all()
    found = {row["dedupe_key"]: row for row in rows}

    for key, item in wanted.items():
        uid = str(item.get("candidate_uid") or "")
        title = str(item.get("title") or "").strip() or "(untitled)"
        row = found.get(key)

        if row is None:
            report.findings.append(
                VerifyFinding(uid, title, "missing", f"no staging row for dedupe_key {key!r}")
            )
            continue

        expected_text = expected_body(item)
        if expected_text and (row["fact_text"] or "") != expected_text:
            report.findings.append(
                VerifyFinding(uid, title, "content_drift", "staged fact_text no longer matches the approved candidate")
            )
            continue

        stamped_pillar = str(item.get("import_requirement_type") or "")
        if stamped_pillar and (row["pillar"] or "") != stamped_pillar:
            report.findings.append(
                VerifyFinding(
                    uid, title, "pillar_drift",
                    f"staged as {row['pillar']!r}, audit stamp says {stamped_pillar!r}",
                )
            )
            continue

        stamped_country = str(item.get("import_country") or "")
        if stamped_country and (row["destination_country"] or "") != stamped_country:
            report.findings.append(
                VerifyFinding(
                    uid, title, "country_drift",
                    f"staged for {row['destination_country']!r}, audit stamp says {stamped_country!r}",
                )
            )
            continue

        report.intact += 1

    return report
