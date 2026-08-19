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

from ...imports.candidate_beam import importer
from ..auth_deps import require_admin
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


class ImportPlanRequest(BaseModel):
    country: str = Field(..., min_length=2, max_length=64)
    #: candidate_uid -> pillar, for the categories that have no grounded mapping. The
    #: selector is a human act; the API will not invent one.
    pillar_overrides: Dict[str, str] = Field(default_factory=dict)


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
            text("SELECT status FROM public.candidate_beam_items WHERE id = CAST(:id AS uuid)"),
            {"id": item_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="candidate not found")
        if row["status"] == "imported":
            raise HTTPException(
                status_code=409,
                detail="candidate already imported — its staged row is the record of that decision",
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
