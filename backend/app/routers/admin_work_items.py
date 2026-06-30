"""
Mission Control demands console API (admin-only).

P1: reads/writes the canonical `work_items` demand store + ingestion/triage.
P2: dispatch — launch the existing autofix agent for one agent-eligible demand
(feature-flagged off by default) + a secret-gated run-status callback. All console
endpoints are admin-gated; the store fails soft on a missing table.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from ..auth_deps import require_admin
from ..services.autofix_dispatch import dispatch_autofix
from ..services.work_item_ingest import build_work_items
from ..services.work_item_triage import classify_demand
from ...database import db

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/work-items", tags=["admin-work-items"])

# Run-status the callback may report → the work_item status it maps to.
_RUN_TO_ITEM_STATUS = {"merged": "done", "deployed": "done", "failed": "blocked", "reverted": "blocked"}


def dispatch_enabled() -> bool:
    return os.getenv("MISSION_CONTROL_DISPATCH_ENABLED", "").lower() in ("1", "true", "yes", "on")


def dispatch_block_reason(auto_fixable: Any, triage_json: Any) -> Optional[str]:
    """None if the demand may be dispatched to the agent; else a human-readable reason.
    Mirrors the autofix safety model: only trivial, non-blocklisted demands qualify."""
    if not auto_fixable:
        return "not agent-eligible (needs a human plan)"
    triage = triage_json
    if isinstance(triage, str):
        try:
            triage = json.loads(triage)
        except ValueError:
            triage = {}
    if isinstance(triage, dict) and triage.get("blocked"):
        return "blocklisted surface — human only"
    return None


def _verify_callback_secret(request: Request) -> None:
    """Mirror crons._verify_cron_secret: fail-closed shared-secret for the workflow callback."""
    expected = os.getenv("CRON_SECRET", "")
    if not expected:
        raise HTTPException(status_code=503, detail="callback not configured")
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="invalid callback secret")

# Sources we ingest in P1 (feedback widget + support tickets); each maps to a
# SELECT of recent rows. ai_feedback / contradiction are an extension point.
_SOURCE_QUERIES = {
    "feedback": "SELECT id, page_url, category, message FROM public.feedback ORDER BY created_at DESC LIMIT 500",
    "support": "SELECT id, subject, raw_content, company_id, from_email FROM public.support_tickets ORDER BY created_at DESC LIMIT 500",
}

_PRIORITY_ORDER = "array_position(ARRAY['P0','P1','P2','P3'], priority)"


def _missing_table(exc: Exception) -> bool:
    blob = str(getattr(exc, "orig", exc)).lower()
    return "42p01" in blob or "does not exist" in blob


class PatchBody(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
def list_work_items(
    status: Optional[str] = None,
    kind: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 200,
    _admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    sql = text(
        f"""
        SELECT id, source, source_url, kind, title, body, reporter_role, company_id,
               status, priority, complexity, auto_fixable, triage_json, dedupe_key,
               pr_url, created_at
        FROM public.work_items
        WHERE (:status IS NULL OR status = :status)
          AND (:kind IS NULL OR kind = :kind)
          AND (:priority IS NULL OR priority = :priority)
        ORDER BY {_PRIORITY_ORDER}, created_at DESC
        LIMIT :limit
        """
    )
    try:
        with db.engine.begin() as conn:
            rows = conn.execute(sql, {"status": status, "kind": kind, "priority": priority, "limit": limit}).mappings().all()
    except ProgrammingError as exc:
        if _missing_table(exc):
            return {"items": [], "table_ready": False}
        raise
    return {"items": [dict(r) for r in rows], "table_ready": True}


@router.get("/{item_id}")
def get_work_item(item_id: str, _admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    try:
        with db.engine.begin() as conn:
            item = conn.execute(
                text("SELECT * FROM public.work_items WHERE id = :id"), {"id": item_id}
            ).mappings().first()
            if item is None:
                raise HTTPException(status_code=404, detail="work item not found")
            runs = conn.execute(
                text("SELECT * FROM public.work_item_runs WHERE work_item_id = :id ORDER BY dispatched_at DESC"),
                {"id": item_id},
            ).mappings().all()
    except ProgrammingError as exc:
        if _missing_table(exc):
            raise HTTPException(status_code=404, detail="work item store not initialised")
        raise
    return {"item": dict(item), "runs": [dict(r) for r in runs]}


@router.patch("/{item_id}")
def patch_work_item(item_id: str, body: PatchBody, _admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=422, detail="no fields to update")
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    fields["id"] = item_id
    with db.engine.begin() as conn:
        updated = conn.execute(
            text(f"UPDATE public.work_items SET {set_clause}, updated_at = now() WHERE id = :id RETURNING id"),
            fields,
        ).first()
    if updated is None:
        raise HTTPException(status_code=404, detail="work item not found")
    return {"ok": True, "id": item_id}


@router.post("/{item_id}/triage")
def retriage_work_item(item_id: str, _admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    with db.engine.begin() as conn:
        row = conn.execute(
            text("SELECT title, body FROM public.work_items WHERE id = :id"), {"id": item_id}
        ).mappings().first()
        if row is None:
            raise HTTPException(status_code=404, detail="work item not found")
        triage = classify_demand(row["title"] or "", row["body"] or "")
        conn.execute(
            text(
                """UPDATE public.work_items
                   SET kind = :kind, priority = :priority, complexity = :complexity,
                       auto_fixable = :auto_fixable, triage_json = CAST(:triage AS jsonb),
                       status = 'triaged', updated_at = now()
                   WHERE id = :id"""
            ),
            {
                "kind": triage["kind"], "priority": triage["priority"], "complexity": triage["complexity"],
                "auto_fixable": triage["auto_fixable"], "triage": json.dumps(triage), "id": item_id,
            },
        )
    return {"ok": True, "triage": triage}


@router.post("/sync")
def sync_work_items(_admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    """Backfill new demands from the intake sources into work_items (idempotent)."""
    inserted = 0
    by_source: Dict[str, int] = {}
    try:
        with db.engine.begin() as conn:
            for source, query in _SOURCE_QUERIES.items():
                try:
                    src_rows = [dict(r) for r in conn.execute(text(query)).mappings().all()]
                except ProgrammingError as exc:
                    if _missing_table(exc):
                        continue  # source table absent in this env — skip
                    raise
                existing = {
                    (source, r[0])
                    for r in conn.execute(
                        text("SELECT source_id FROM public.work_items WHERE source = :s AND source_id IS NOT NULL"),
                        {"s": source},
                    ).all()
                }
                new_items = build_work_items(source, src_rows, frozenset(existing))
                for wi in new_items:
                    conn.execute(
                        text(
                            """INSERT INTO public.work_items
                               (id, source, source_id, source_url, kind, title, body, reporter_role,
                                company_id, status, priority, complexity, auto_fixable, triage_json, dedupe_key)
                               VALUES (:id, :source, :source_id, :source_url, :kind, :title, :body, :reporter_role,
                                :company_id, :status, :priority, :complexity, :auto_fixable, CAST(:triage_json AS jsonb), :dedupe_key)
                               ON CONFLICT (source, source_id) WHERE source_id IS NOT NULL DO NOTHING"""
                        ),
                        {**wi, "id": str(uuid.uuid4()), "triage_json": json.dumps(wi["triage_json"])},
                    )
                    inserted += 1
                by_source[source] = len(new_items)
    except ProgrammingError as exc:
        if _missing_table(exc):
            return {"ok": False, "table_ready": False, "inserted": 0}
        raise
    return {"ok": True, "inserted": inserted, "by_source": by_source}


# ── P2: dispatch (launch the agent) + run-status callback ────────────────────


class CallbackBody(BaseModel):
    status: str
    pr_url: Optional[str] = None
    github_run_url: Optional[str] = None


@router.post("/{item_id}/dispatch")
def dispatch_work_item(item_id: str, _admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    """Launch the autofix agent for one agent-eligible demand (feature-flagged off
    by default; reuses the existing Supabase edge function → autofix-validate)."""
    if not dispatch_enabled():
        raise HTTPException(status_code=503, detail="dispatch is disabled (MISSION_CONTROL_DISPATCH_ENABLED)")

    with db.engine.begin() as conn:
        item = conn.execute(
            text("SELECT id, title, body, auto_fixable, triage_json FROM public.work_items WHERE id = :id"),
            {"id": item_id},
        ).mappings().first()
        if item is None:
            raise HTTPException(status_code=404, detail="work item not found")

        block = dispatch_block_reason(item["auto_fixable"], item["triage_json"])
        if block is not None:
            raise HTTPException(status_code=409, detail=block)

        result = dispatch_autofix({"id": str(item["id"]), "title": item["title"], "body": item["body"] or ""})
        run_id = str(uuid.uuid4())
        run_status = "pr_opened" if result.get("pr_url") else ("queued" if result.get("ok") else "failed")
        conn.execute(
            text(
                """INSERT INTO public.work_item_runs (id, work_item_id, dispatched_by, status, pr_url)
                   VALUES (:id, :wid, :by, :status, :pr)"""
            ),
            {"id": run_id, "wid": item_id, "by": str(_admin.get("id") or ""), "status": run_status, "pr": result.get("pr_url")},
        )
        conn.execute(
            text(
                """UPDATE public.work_items
                   SET status = 'dispatched', last_run_id = :rid, pr_url = COALESCE(:pr, pr_url), updated_at = now()
                   WHERE id = :id"""
            ),
            {"rid": run_id, "pr": result.get("pr_url"), "id": item_id},
        )

    return {"ok": bool(result.get("ok")), "run_id": run_id, "pr_url": result.get("pr_url"), "result": result}


@router.post("/{item_id}/run-callback")
def run_callback(item_id: str, body: CallbackBody, request: Request) -> Dict[str, Any]:
    """The autofix workflow reports run progress here (secret-gated, not admin-auth)."""
    _verify_callback_secret(request)
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """UPDATE public.work_item_runs
                   SET status = :status, pr_url = COALESCE(:pr, pr_url),
                       github_run_url = COALESCE(:run_url, github_run_url), updated_at = now()
                   WHERE work_item_id = :id
                     AND id = (SELECT last_run_id FROM public.work_items WHERE id = :id)"""
            ),
            {"status": body.status, "pr": body.pr_url, "run_url": body.github_run_url, "id": item_id},
        )
        item_status = _RUN_TO_ITEM_STATUS.get(body.status)
        if item_status:
            conn.execute(
                text("UPDATE public.work_items SET status = :s, pr_url = COALESCE(:pr, pr_url), updated_at = now() WHERE id = :id"),
                {"s": item_status, "pr": body.pr_url, "id": item_id},
            )
    return {"ok": True}
