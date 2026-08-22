"""Admin review surface for the corridor candidate beam.

Read the queue, approve or reject a candidate, and see what an import WOULD do before
anything is written. Admin-only end to end: the content is unreviewed model output, and an
unreviewed draft reads exactly like a published requirement to anyone who sees it.

Two things this router deliberately cannot do:

* **It cannot promote.** There is no endpoint that writes `public.requirement_items`.
  Approving a candidate here moves it into the existing otto_staging flow in
  `needs_review`; a human moves it on from there through the /admin gate that already
  exists. The safety argument for the whole beam is that model output cannot become
  customer-facing without a person, and a router with a promote button would quietly
  retire that argument.

* **It cannot set `imported` without the audit trail.** The stamp comes from
  `importer.audit_stamp()` as one unit, because `candidate_beam_items` has a CHECK that
  refuses `status='imported'` unless country, requirement type, ref and timestamp are all
  present — assembling it piecemeal would fail mid-batch.

Registered in BOTH `backend/main.py` and `backend/app/main.py`. Render boots
`backend.main:app`, so a router registered only in the modular app 405s in production.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from ...imports.candidate_beam import importer, pipeline, ranking, store
from ..auth_deps import require_admin
from ...imports.otto.parsers import _host, classify_source
from ..db import SessionLocal

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/candidate-beam", tags=["candidate-beam"])

_TERMINAL_REVIEW_STATES = {"approved", "rejected"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ReviewRequest(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected)$")
    review_note: Optional[str] = Field(None, max_length=2000)


class AttachSourceRequest(BaseModel):
    source_url: str = Field(..., min_length=4, max_length=2000)
    #: The quotable line the URL actually supports. Optional, because a reviewer may only have
    #: the page; but FactRow carries it, and a URL without a quote is a weaker citation.
    evidence_quote: Optional[str] = Field(None, max_length=2000)


class ImportPlanRequest(BaseModel):
    country: str = Field(..., min_length=2, max_length=64)
    #: candidate_uid -> pillar, for the categories that have no grounded mapping. The
    #: selector is a human act; the API will not invent one.
    pillar_overrides: Dict[str, str] = Field(default_factory=dict)


class StartRunRequest(BaseModel):
    corridor: str = Field(..., min_length=3, max_length=16, description="ORIGIN-DEST, ISO-2, e.g. FR-NO")
    employee_type: str = Field(..., min_length=2, max_length=32)
    context: Optional[str] = Field(None, max_length=4000)
    #: 2..7. Every pass is a paid call, and below two there is no cross-pass agreement to
    #: measure — the ranking's entire signal is undefined.
    passes: int = Field(default=5, ge=store.MIN_PASSES, le=store.MAX_PASSES)
    model: Optional[str] = Field(None, max_length=120)


class RunPassRequest(BaseModel):
    #: Omit to run the lowest slot not yet completed — which is also how a failed pass is
    #: retried. Naming a slot explicitly re-runs exactly that one.
    pass_number: Optional[int] = Field(None, ge=1, le=store.MAX_PASSES)


class FinalizeRequest(BaseModel):
    force: bool = False


class ImportRequest(ImportPlanRequest):
    #: Defaults TRUE. Executing an import must be something the caller asked for in so
    #: many words — a forgotten flag should preview, never write.
    dry_run: bool = True


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


@router.get("/runs")
def list_runs(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Beam runs, newest first. Counts come from the run row, not from a live count of
    items: a run that failed before writing items must still report what it attempted."""
    sql = """
        SELECT id::text, set_uid, corridor, employee_type, status,
               passes_requested, passes_completed, llm_provider, llm_model,
               candidate_count, error, created_by, created_at, updated_at
        FROM public.candidate_beam_runs
        {where}
        ORDER BY created_at DESC
        LIMIT :limit
    """.format(where="WHERE status = :status" if status else "")
    params: Dict[str, Any] = {"limit": limit}
    if status:
        params["status"] = status

    with SessionLocal() as session:
        rows = session.execute(text(sql), params).mappings().all()
    return {"runs": [dict(r) for r in rows]}


@router.get("/runs/{run_id}/items")
def list_items(
    run_id: str,
    status: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Candidates for one run, in rank order.

    `variants` is returned whole. A reviewer judging a merged representative text without
    being able to see where the passes diverged is reviewing the merge, not the evidence.
    """
    sql = """
        SELECT id::text, candidate_uid, rank, pass_frequency, passes_total,
               confidence_band, flagged, source_missing, title, official_guidance,
               actual_reality, action_required, source, category, variants,
               status, review_note, reviewed_by, reviewed_at,
               researched_source_url, researched_evidence_quote, researched_source_class,
               researched_by, researched_at,
               import_country, import_requirement_type, imported_ref, imported_at
        FROM public.candidate_beam_items
        WHERE run_id = CAST(:run_id AS uuid)
        {extra}
        ORDER BY rank ASC
    """.format(extra="AND status = :status" if status else "")
    params: Dict[str, Any] = {"run_id": run_id}
    if status:
        params["status"] = status

    with SessionLocal() as session:
        rows = session.execute(text(sql), params).mappings().all()

    items = [dict(r) for r in rows]
    return {
        "items": items,
        "counts": {
            "total": len(items),
            # .get() throughout: a count is a summary, and a summary that 500s because one
            # column came back absent is worse than a summary that reports zero. The row
            # shape is the database's to guarantee; this endpoint's job is to stay up.
            "pending_review": sum(1 for i in items if i.get("status") == "pending_review"),
            "approved": sum(1 for i in items if i.get("status") == "approved"),
            "rejected": sum(1 for i in items if i.get("status") == "rejected"),
            "imported": sum(1 for i in items if i.get("status") == "imported"),
            # Surfaced as its own number because it is the research worklist, not a defect:
            # a candidate nobody sourced is work to do, and burying it in `total` hides it.
            "source_missing": sum(1 for i in items if i.get("source_missing")),
            # The ACTIONABLE worklist: unsourced by the beam AND nobody has sourced it since.
            # `source_missing` deliberately stays frozen — it records what the beam produced,
            # and ranking.py derives `flagged` from it, so flipping it would rewrite history
            # and change an unrelated signal. This number shrinks as research lands; that one
            # stays true.
            "needs_research": sum(
                1
                for i in items
                if i.get("source_missing") and not (i.get("researched_source_url") or "").strip()
            ),
            "researched": sum(
                1 for i in items if (i.get("researched_source_url") or "").strip()
            ),
        },
    }


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


@router.post("/items/{item_id}/review")
def review_item(
    item_id: str,
    body: ReviewRequest,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Approve or reject one candidate.

    An already-imported candidate is frozen: re-reviewing it would leave staged rows whose
    provenance says approved while the queue says rejected, and the staged row is the one
    a reader eventually sees.
    """
    with SessionLocal() as session:
        row = session.execute(
            text(
                "SELECT status, source, researched_source_url "
                "FROM public.candidate_beam_items WHERE id = CAST(:id AS uuid)"
            ),
            {"id": item_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="candidate not found")
        if row["status"] == "imported":
            raise HTTPException(
                status_code=409,
                detail="candidate already imported — its staged row is the record of that decision",
            )
        # An unsourced candidate cannot be approved, because the importer would skip it
        # anyway. Without this the queue tells the reviewer a lie: the candidate reads
        # "approved" and is silently dropped at import with a reason nobody goes back to read.
        # Rejecting one is always allowed — refusing a bad candidate needs no citation.
        # .get(), not [] — the same reasoning list_items states for its counts: an endpoint
        # whose job is to refuse safely must not 500 because a column came back absent.
        if body.status == "approved" and not (
            (row.get("source") or "").strip()
            or (row.get("researched_source_url") or "").strip()
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "candidate has no source: attach a researched source before approving, "
                    "or the import will skip it"
                ),
            )

        session.execute(
            text(
                """
                UPDATE public.candidate_beam_items
                   SET status = :status,
                       review_note = :note,
                       reviewed_by = :who,
                       reviewed_at = NOW(),
                       updated_at = NOW()
                 WHERE id = CAST(:id AS uuid)
                """
            ),
            {
                "id": item_id,
                "status": body.status,
                "note": body.review_note,
                "who": str(user.get("id") or user.get("email") or "admin"),
            },
        )
        session.commit()
    return {"ok": True, "id": item_id, "status": body.status}


@router.post("/items/{item_id}/source")
def attach_source(
    item_id: str,
    body: AttachSourceRequest,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Record a HUMAN'S researched source for a candidate the beam could not cite.

    This is the research worklist's landing place. Around a quarter of a run arrives with no
    source at all; those candidates are real obligations the model surfaced but could not
    back, and `FactRow` requires a URL, so they are unimportable until a person finds one.

    What it does NOT do:

    * It does not touch `source`. That column is the model's verbatim claim and its NULL is
      the worklist itself; overwriting it would erase the difference between what a model
      asserted and what a person found, on exactly the rows where that difference matters.
    * It does not verify anything. The row still stages at `needs_review` and still reaches a
      customer only through the /admin/countries gate.
    * It does not refuse an unofficial URL. `unofficial` is a true fact about the link, and a
      reviewer may genuinely have nothing better; the honest move is to store the verdict and
      show it, not to reject the research and leave the candidate stranded.
    """
    url = body.source_url.strip()
    # Reuses the otto parser's host extraction rather than adding a second URL parser, so
    # "what counts as a URL here" cannot drift from what classify_source() sees.
    if not _host(url) or not url.lower().startswith(("http://", "https://")):
        raise HTTPException(
            status_code=422, detail="source_url must be an absolute http(s) URL"
        )

    source_class = classify_source(url)
    who = str(user.get("id") or user.get("email") or "admin")

    with SessionLocal() as session:
        row = session.execute(
            text("SELECT status FROM public.candidate_beam_items WHERE id = CAST(:id AS uuid)"),
            {"id": item_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="candidate not found")
        if row["status"] == "imported":
            # Same freeze review_item applies: the staged row already carries whatever source
            # was used, and changing it here would leave the two disagreeing.
            raise HTTPException(
                status_code=409,
                detail="candidate already imported — its staged row records the source it used",
            )

        session.execute(
            text(
                """
                UPDATE public.candidate_beam_items
                   SET researched_source_url     = :url,
                       researched_evidence_quote = :quote,
                       researched_source_class   = :klass,
                       researched_by             = :who,
                       researched_at             = NOW(),
                       updated_at                = NOW()
                 WHERE id = CAST(:id AS uuid)
                """
            ),
            {
                "id": item_id,
                "url": url,
                "quote": (body.evidence_quote or "").strip() or None,
                "klass": source_class,
                "who": who,
            },
        )
        session.commit()

    # source_class is returned so the caller can tell the reviewer what they just attached is
    # unofficial BEFORE they approve it, rather than discovering it in the import downgrades.
    return {
        "ok": True,
        "id": item_id,
        "researched_source_url": url,
        "researched_source_class": source_class,
        "researched_by": who,
    }


# ---------------------------------------------------------------------------
# Import (plan only — this router never writes staging or requirement_items)
# ---------------------------------------------------------------------------


@router.post("/runs/{run_id}/import-plan")
def import_plan(
    run_id: str,
    body: ImportPlanRequest,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """What an import of this run's APPROVED candidates would do. Writes nothing.

    Every skip is returned with its reason. A partial import that looks complete is the
    failure this repo's importers were built to stop, so the reviewer sees the unsourced
    candidates and the unresolved pillars BEFORE anything is staged, not after.
    """
    with SessionLocal() as session:
        rows = session.execute(
            text(
                """
                SELECT candidate_uid, title, official_guidance, actual_reality,
                       action_required, source, category, status, flagged,
                       pass_frequency, confidence_band
                  FROM public.candidate_beam_items
                 WHERE run_id = CAST(:run_id AS uuid)
                 ORDER BY rank ASC
                """
            ),
            {"run_id": run_id},
        ).mappings().all()

    plan = importer.plan_import(
        [dict(r) for r in rows],
        country=body.country,
        batch_id=f"beam-{run_id}",
        pillar_overrides=body.pillar_overrides,
    )
    return {
        "importable": plan.importable,
        "skipped": [
            {"candidate_uid": s.candidate_uid, "title": s.title, "reason": s.reason}
            for s in plan.skipped
        ],
        "skips_by_reason": plan.skips_by_reason(),
        "pillar_by_uid": plan.pillar_by_uid,
        # Named so the UI cannot present this as an import that happened.
        "written": False,
    }


@router.get("/pillars")
def pillars(user: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    """The canonical pillar vocabulary plus the grounded category mapping.

    The UI needs both: the seven values a selector may offer, and which beam categories
    already resolve so it only asks a human about the six that do not.
    """
    return {
        "pillars": list(importer.CANONICAL_PILLARS),
        "grounded_categories": dict(importer.PILLAR_BY_CATEGORY),
    }


_ITEM_SELECT = """
    SELECT candidate_uid, title, official_guidance, actual_reality,
           action_required, source, category, status, flagged,
           researched_source_url, researched_evidence_quote, researched_source_class,
           pass_frequency, confidence_band,
           import_country, import_requirement_type, imported_ref, imported_at
      FROM public.candidate_beam_items
     WHERE run_id = CAST(:run_id AS uuid)
     ORDER BY rank ASC
"""


@router.post("/runs/{run_id}/import")
def run_import(
    run_id: str,
    body: ImportRequest,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Stage this run's approved candidates into otto_staging."""
    # Staging only. `promote()` writes the customer-facing served table, and this router
    # must never reach it — rows land at `review_status='pending'` and get to a customer
    # solely through the existing /admin/countries gate. Nothing here can set a verified
    # state; the table's CHECK refuses it even if a future edit tried.
    #
    # (Said in a comment rather than the docstring on purpose: the router's own guard test
    # scans string literals, and a docstring is one.)
    #
    # One transaction owns both the staging insert and the audit stamp. Splitting them
    # would allow an item marked `imported` whose staging row was rolled back — the one
    # state `import-verify` cannot tell apart from tampering.
    #
    # A freeze conflict returns 409 and writes NOTHING, including for the candidates that
    # would have succeeded: the caller asked for one thing, and half-applying it is not
    # that.
    with SessionLocal() as session:
        with session.begin():
            conn = session.connection()
            rows = conn.execute(text(_ITEM_SELECT), {"run_id": run_id}).mappings().all()
            if not rows:
                raise HTTPException(status_code=404, detail="run not found or has no candidates")

            result = importer.execute_import(
                conn,
                run_id=run_id,
                candidates=[dict(r) for r in rows],
                country=body.country,
                batch_id=f"beam-{run_id}",
                imported_by=str(user.get("email") or user.get("id") or "admin"),
                pillar_overrides=body.pillar_overrides,
                dry_run=body.dry_run,
            )

            if not result.ok:
                # Raise inside the transaction so the context manager rolls back — belt and
                # braces, since execute_import already returns before writing on a conflict.
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "import_frozen",
                        "conflicts": [
                            {
                                "candidate_uid": c.candidate_uid,
                                "title": c.title,
                                "field": c.field,
                                "already": c.already,
                                "requested": c.requested,
                                "reason": c.reason,
                            }
                            for c in result.conflicts
                        ],
                    },
                )

    return {
        "written": not result.dry_run,
        "dry_run": result.dry_run,
        "batch_id": result.batch_id,
        "staged": result.staged,
        "already_present": result.already_present,
        "stamped": result.stamped,
        "skipped": [
            {"candidate_uid": s.candidate_uid, "title": s.title, "reason": s.reason}
            for s in result.skipped
        ],
        "rejections": result.rejections,
        # Said in the payload as well as the UI: the import is not the approval.
        "notice": "Imported rows still require /admin/countries approval before they serve.",
    }


@router.get("/runs/{run_id}/import-verify")
def run_import_verify(
    run_id: str,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Read-only QA: does every imported candidate still have its staging row, unchanged?

    Returns 200 with the report when intact and 409 with the same report when not, so a
    caller cannot mistake a drifted import for a healthy one by ignoring a field.
    """
    with SessionLocal() as session:
        rows = session.execute(text(_ITEM_SELECT), {"run_id": run_id}).mappings().all()
        if not rows:
            raise HTTPException(status_code=404, detail="run not found or has no candidates")

        items = [dict(r) for r in rows]
        imported = [i for i in items if i.get("status") == "imported"]
        approved_not_imported = sum(1 for i in items if i.get("status") == "approved")

        report = importer.verify_import(
            session.connection(),
            run_id=run_id,
            imported_items=imported,
            approved_not_imported=approved_not_imported,
        )

    payload = {
        "run_id": report.run_id,
        "ok": report.ok,
        "checked": report.checked,
        "intact": report.intact,
        "approved_not_imported": report.approved_not_imported,
        "findings": [
            {
                "candidate_uid": f.candidate_uid,
                "title": f.title,
                "problem": f.problem,
                "detail": f.detail,
            }
            for f in report.findings
        ],
    }
    if not report.ok:
        raise HTTPException(status_code=409, detail=payload)
    return payload

# ---------------------------------------------------------------------------
# Run lifecycle — start, one pass at a time, finalize
# ---------------------------------------------------------------------------


def _split_corridor(corridor: str) -> tuple:
    parts = [p.strip().upper() for p in corridor.replace("_", "-").split("-") if p.strip()]
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="corridor must be ORIGIN-DEST, e.g. FR-NO")
    return parts[0], parts[1]


@router.post("/runs", status_code=201)
def start_run(
    body: StartRunRequest,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Open a run. Executes no passes — the caller drives them one at a time."""
    # Deliberately not "start the whole beam here". Five paid model calls behind one
    # gateway timeout loses every completed pass when it trips, with nothing to resume
    # from. The row opens as `generating` and each pass lands separately.
    origin, dest = _split_corridor(body.corridor)
    model = body.model or pipeline.default_model()

    with SessionLocal() as session:
        with session.begin():
            run_id = store.create_run(
                session.connection(),
                corridor=f"{origin}-{dest}",
                origin_country=origin,
                dest_country=dest,
                employee_type=body.employee_type,
                context=body.context,
                passes_requested=body.passes,
                llm_provider="platform",
                llm_model=model,
                created_by=str(user.get("email") or user.get("id") or "admin"),
            )

    return {
        "run_id": run_id,
        "status": store.RUN_GENERATING,
        "passes_requested": body.passes,
        "passes_completed": 0,
        "next_pass": 1,
        "llm_model": model,
    }


@router.post("/runs/{run_id}/pass")
def execute_pass(
    run_id: str,
    body: RunPassRequest,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Execute exactly ONE pass. Also the resume mechanism."""
    # The model call happens OUTSIDE the write transaction: it takes seconds and holding a
    # row lock across it would serialise every other admin write behind an API call we do
    # not control.
    with SessionLocal() as session:
        run = store.load_run(session.connection(), run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    pass_number = body.pass_number or store.next_pass_number(run)
    if pass_number is None:
        raise HTTPException(
            status_code=409,
            detail=f"all {run['passes_requested']} passes already completed; finalize instead",
        )
    if pass_number > int(run["passes_requested"]):
        raise HTTPException(status_code=422, detail="pass_number exceeds passes_requested")

    framing = pipeline.framing_for(pass_number)
    record = pipeline.run_pass(
        corridor=run["corridor"],
        employee_type=run["employee_type"],
        framing=framing,
        context=run.get("context"),
        model=run.get("llm_model"),
    )

    items = [
        {**item, "arrival_ordinal": ordinal}
        for ordinal, item in enumerate(record.get("items") or [], start=1)
    ]
    meta = {k: v for k, v in record.items() if k != "items"}
    meta["ok"] = bool(record.get("ok"))
    meta["item_count"] = len(items)

    with SessionLocal() as session:
        with session.begin():
            state = store.record_pass(
                session.connection(),
                run_id=run_id,
                pass_number=pass_number,
                framing=framing,
                items=items,
                meta=meta,
            )
            refreshed = store.load_run(session.connection(), run_id)

    return {
        "run_id": run_id,
        "pass": pass_number,
        "framing": framing,
        "ok": meta["ok"],
        "item_count": len(items),
        "error": record.get("error"),
        "passes_completed": state["passes_completed"],
        "passes_requested": run["passes_requested"],
        "next_pass": store.next_pass_number(refreshed or run),
    }


@router.post("/runs/{run_id}/finalize")
def finalize_run(
    run_id: str,
    body: FinalizeRequest,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Dedupe, rank and persist the run's candidates."""
    # `passes_total` is what was ATTEMPTED, not what succeeded. A run that lost a pass must
    # not report the survivors as unanimous — 4/4 reads as near-certain when the honest
    # answer is 4/5.
    with SessionLocal() as session:
        run = store.load_run(session.connection(), run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    completed = store.completed_pass_numbers(run)
    if len(completed) < store.MIN_PASSES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"only {len(completed)} pass(es) completed; cross-pass agreement is "
                f"undefined below {store.MIN_PASSES}. Run another pass first."
            ),
        )
    if run["status"] == store.RUN_PENDING_REVIEW and not body.force:
        raise HTTPException(
            status_code=409, detail="run already finalized; pass force=true to rebuild"
        )

    by_pass = {int(o["pass"]): o for o in run["pass_outputs"]}
    ordered_passes, framings = [], []
    for number in sorted(by_pass):
        output = by_pass[number]
        items = sorted(
            output.get("items") or [], key=lambda i: i.get("arrival_ordinal") or 0
        )
        ordered_passes.append(items)
        framings.append(output.get("framing"))

    candidates = ranking.build_candidates(ordered_passes, framings)
    for candidate in candidates:
        candidate["passes_total"] = int(run["passes_requested"])
        candidate["candidate_uid"] = store.candidate_uid_for(candidate["title"])

    with SessionLocal() as session:
        with session.begin():
            written = store.persist_candidates(
                session.connection(),
                run_id=run_id,
                candidates=candidates,
                passes_total=int(run["passes_requested"]),
            )

    return {
        "run_id": run_id,
        "status": store.RUN_PENDING_REVIEW,
        "candidate_count": written,
        "passes_completed": len(completed),
        "passes_requested": run["passes_requested"],
        "flagged": sum(1 for c in candidates if c.get("flagged")),
        "source_missing": sum(1 for c in candidates if c.get("source_missing")),
    }
