"""
Admin LinkedIn Outreach CRM router.

Backend proxy for the outreach feature's tables (`linkedin_prospects`,
`message_templates`, `prospect_replies`, `outreach_messages`). These used to be
queried directly from the browser via the Supabase client, which required a live
Supabase `authenticated` session — but ReloPass admins hold a ReloPass session
token, not a Supabase JWT, so the query ran as `anon` and Postgres denied it
("permission denied for table linkedin_prospects"). Serving the data through this
admin-gated router (service_role via SessionLocal, `require_admin`) removes the
Supabase-session dependency entirely and matches the "data goes through the API"
rule in CLAUDE.md. Mirrors backend/app/routers/admin_prospects.py.
"""
from __future__ import annotations

import logging
import uuid as _uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from ..auth_deps import require_admin
from ..db import SessionLocal

log = logging.getLogger(__name__)

router = APIRouter(prefix="/outreach", tags=["admin-outreach"])

# Column whitelists — only these may be written per table. Names are validated
# against these sets before being interpolated into SQL (values are always bound).
_PROSPECT_COLS = {
    "full_name", "linkedin_url", "profile_headline", "company_name", "company_size",
    "job_title", "corridor_relevance", "notes", "source", "status",
    "message_sent_at", "last_reply_at", "follow_up_sent_at", "converted_at",
}
_TEMPLATE_COLS = {"name", "message_type", "body_template", "is_active"}
_REPLY_COLS = {
    "prospect_id", "reply_text", "replied_at", "sentiment",
    "next_action", "next_action_due", "outreach_message_id",
}
_MESSAGE_COLS = {
    "prospect_id", "message_type", "subject_line", "body", "personalisation_notes",
    "status", "approved_at", "sent_at", "copied_to_clipboard_at",
}


def _coerce(v: Any) -> Any:
    """uuid -> str (Postgres returns uuid columns as uuid.UUID), datetime -> isoformat."""
    if isinstance(v, _uuid.UUID):
        return str(v)
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()
        except Exception:
            return str(v)
    return v


def _row(m: Any) -> Dict[str, Any]:
    return {k: _coerce(v) for k, v in dict(m).items()}


def _list(table: str, where: str = "", order: str = "created_at DESC",
          params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    sql = text(f"SELECT * FROM public.{table} {('WHERE ' + where) if where else ''} ORDER BY {order}")
    with SessionLocal() as db:
        return [_row(r) for r in db.execute(sql, params or {}).mappings().all()]


def _insert(table: str, allowed: set, payload: Dict[str, Any]) -> Dict[str, Any]:
    cols = [k for k in payload.keys() if k in allowed]
    if not cols:
        raise HTTPException(status_code=400, detail="no valid fields to insert")
    collist = ", ".join(cols)
    vallist = ", ".join(f":{c}" for c in cols)
    sql = text(f"INSERT INTO public.{table} ({collist}) VALUES ({vallist}) RETURNING *")
    with SessionLocal() as db:
        m = db.execute(sql, {c: payload[c] for c in cols}).mappings().first()
        db.commit()
    return _row(m)


def _update(table: str, allowed: set, row_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    cols = [k for k in patch.keys() if k in allowed]
    with SessionLocal() as db:
        if cols:
            setlist = ", ".join(f"{c} = :{c}" for c in cols)
            sql = text(f"UPDATE public.{table} SET {setlist} WHERE id = :__id RETURNING *")
            params = {c: patch[c] for c in cols}
            params["__id"] = row_id
            m = db.execute(sql, params).mappings().first()
            db.commit()
        else:
            m = db.execute(
                text(f"SELECT * FROM public.{table} WHERE id = :__id"), {"__id": row_id}
            ).mappings().first()
    if not m:
        raise HTTPException(status_code=404, detail="not found")
    return _row(m)


def _delete(table: str, row_id: str) -> Dict[str, Any]:
    with SessionLocal() as db:
        res = db.execute(
            text(f"DELETE FROM public.{table} WHERE id = :__id RETURNING id"), {"__id": row_id}
        ).mappings().first()
        db.commit()
    if not res:
        raise HTTPException(status_code=404, detail="not found")
    return {"deleted": row_id}


# ── Prospects ────────────────────────────────────────────────────────────────
@router.get("/prospects")
def list_prospects(_: dict = Depends(require_admin)) -> List[Dict[str, Any]]:
    return _list("linkedin_prospects", order="created_at DESC")


@router.post("/prospects")
def create_prospect(payload: Dict[str, Any], _: dict = Depends(require_admin)) -> Dict[str, Any]:
    return _insert("linkedin_prospects", _PROSPECT_COLS, payload)


@router.patch("/prospects/{prospect_id}")
def update_prospect(prospect_id: str, payload: Dict[str, Any],
                    _: dict = Depends(require_admin)) -> Dict[str, Any]:
    return _update("linkedin_prospects", _PROSPECT_COLS, prospect_id, payload)


@router.delete("/prospects/{prospect_id}")
def delete_prospect(prospect_id: str, _: dict = Depends(require_admin)) -> Dict[str, Any]:
    return _delete("linkedin_prospects", prospect_id)


# ── Templates ────────────────────────────────────────────────────────────────
@router.get("/templates")
def list_templates(_: dict = Depends(require_admin)) -> List[Dict[str, Any]]:
    return _list("message_templates", order="created_at ASC")


@router.post("/templates")
def create_template(payload: Dict[str, Any], _: dict = Depends(require_admin)) -> Dict[str, Any]:
    return _insert("message_templates", _TEMPLATE_COLS, payload)


@router.patch("/templates/{template_id}")
def update_template(template_id: str, payload: Dict[str, Any],
                    _: dict = Depends(require_admin)) -> Dict[str, Any]:
    return _update("message_templates", _TEMPLATE_COLS, template_id, payload)


@router.delete("/templates/{template_id}")
def delete_template(template_id: str, _: dict = Depends(require_admin)) -> Dict[str, Any]:
    return _delete("message_templates", template_id)


# ── Replies ──────────────────────────────────────────────────────────────────
@router.get("/replies")
def list_replies(prospect_id: str = Query(...),
                 _: dict = Depends(require_admin)) -> List[Dict[str, Any]]:
    return _list("prospect_replies", where="prospect_id = :pid",
                 order="replied_at DESC", params={"pid": prospect_id})


@router.post("/replies")
def create_reply(payload: Dict[str, Any], _: dict = Depends(require_admin)) -> Dict[str, Any]:
    return _insert("prospect_replies", _REPLY_COLS, payload)


# ── Messages ─────────────────────────────────────────────────────────────────
@router.get("/messages")
def list_messages(prospect_id: str = Query(...), status: Optional[str] = Query(None),
                  _: dict = Depends(require_admin)) -> List[Dict[str, Any]]:
    if status:
        return _list("outreach_messages", where="prospect_id = :pid AND status = :st",
                     order="created_at DESC", params={"pid": prospect_id, "st": status})
    return _list("outreach_messages", where="prospect_id = :pid",
                 order="created_at DESC", params={"pid": prospect_id})


@router.post("/messages")
def create_message(payload: Dict[str, Any], _: dict = Depends(require_admin)) -> Dict[str, Any]:
    return _insert("outreach_messages", _MESSAGE_COLS, payload)


@router.patch("/messages/{message_id}")
def update_message(message_id: str, payload: Dict[str, Any],
                   _: dict = Depends(require_admin)) -> Dict[str, Any]:
    return _update("outreach_messages", _MESSAGE_COLS, message_id, payload)
