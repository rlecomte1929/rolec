"""
Mission Control P1 — the demands console API (admin-only).

Reads/writes the canonical `work_items` demand store and runs ingestion + triage.
No execution here (that's P2 dispatch). All endpoints are admin-gated. The store is
committed-not-applied until the migration lands out-of-band, so every read fails
soft (returns empty) on a missing table rather than 500-ing the console.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from ..auth_deps import require_admin
from ..services.work_item_ingest import build_work_items
from ..services.work_item_triage import classify_demand
from ...database import db

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/work-items", tags=["admin-work-items"])

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
