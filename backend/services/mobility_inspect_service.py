"""
Admin inspect: audit log rows related to a mobility_cases.id (Postgres jsonb-aware),
plus compact operational summary (readiness, evaluation snapshot, next actions).
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import ProgrammingError

from .next_action_service import NextActionService
from .passport_case_document_sync_service import GRAPH_PASSPORT_DOCUMENT_KEY

log = logging.getLogger(__name__)


def _coerce_json(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        t = value.strip()
        if not t:
            return {}
        try:
            o = json.loads(t)
            return dict(o) if isinstance(o, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _assignment_id_for_mobility_case(conn: Connection, mobility_case_id: str) -> Optional[str]:
    mid = (mobility_case_id or "").strip()
    if not mid:
        return None
    try:
        row = conn.execute(
            text(
                "SELECT assignment_id FROM assignment_mobility_links "
                "WHERE mobility_case_id = :mid LIMIT 1"
            ),
            {"mid": mid},
        ).mappings().first()
    except ProgrammingError:
        return None
    if not row:
        return None
    aid = row.get("assignment_id")
    return str(aid).strip() if aid is not None else None


def _employee_person_row(people: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for p in people:
        if (p.get("role") or "").strip() == "employee":
            return p
    return None


def _passport_document_row(documents: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for d in documents:
        if (d.get("document_key") or "").strip() == GRAPH_PASSPORT_DOCUMENT_KEY:
            return d
    return None


def _employee_snapshot(person: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    empty = {
        "full_name": None,
        "email": None,
        "nationality": None,
        "residence_country": None,
        "passport_country": None,
    }
    if not person:
        return dict(empty)
    meta = _coerce_json(person.get("metadata"))
    fn = meta.get("full_name")
    if not fn and (meta.get("first_name") or meta.get("last_name")):
        fn = " ".join(
            x for x in (meta.get("first_name"), meta.get("last_name")) if x
        ).strip() or None
    return {
        "full_name": fn if fn else None,
        "email": meta.get("email") if meta.get("email") else None,
        "nationality": meta.get("nationality") if meta.get("nationality") else None,
        "residence_country": meta.get("residence_country") if meta.get("residence_country") else None,
        "passport_country": meta.get("passport_country") if meta.get("passport_country") else None,
    }


def _passport_document_snapshot(doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = {
        "document_key": None,
        "document_status": None,
        "source_evidence_id": None,
        "submitted_at": None,
    }
    if not doc:
        return base
    meta = _coerce_json(doc.get("metadata"))
    out = {
        "document_key": doc.get("document_key"),
        "document_status": doc.get("document_status"),
        "source_evidence_id": meta.get("case_evidence_id"),
        "submitted_at": meta.get("submitted_at"),
    }
    return out


def _rule_code_map(conn: Connection, rule_ids: List[str]) -> Dict[str, str]:
    ids = [r for r in {x.strip() for x in rule_ids if x and str(x).strip()}]
    if not ids:
        return {}
    try:
        parts: List[str] = []
        params: Dict[str, Any] = {}
        for i, rid in enumerate(ids):
            key = f"r{i}"
            parts.append(f":{key}")
            params[key] = rid
        sql = "SELECT id, rule_code FROM policy_rules WHERE id IN (" + ",".join(parts) + ")"
        rows = conn.execute(text(sql), params).mappings().all()
    except ProgrammingError:
        return {}
    return {str(r["id"]): str(r["rule_code"]) for r in rows if r.get("id") is not None}


def _norm_ts(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    s = str(value).strip()
    return s if s else None


def build_mobility_operational_inspect(conn: Connection, mobility_case_id: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compact operational payload for admin inspect (read-only except evaluate is separate POST).
    Expects ctx from CaseContextService.fetch for the same mobility_case_id with case_found True.
    """
    cid = (mobility_case_id or "").strip()
    people: List[Dict[str, Any]] = list(ctx.get("people") or [])
    documents: List[Dict[str, Any]] = list(ctx.get("documents") or [])
    evaluations: List[Dict[str, Any]] = list(ctx.get("evaluations") or [])

    assignment_id = _assignment_id_for_mobility_case(conn, cid)
    has_link = assignment_id is not None
    bridge_status = "linked" if has_link else "missing"

    emp_row = _employee_person_row(people)
    pass_doc = _passport_document_row(documents)

    readiness_flags = {
        "has_mobility_link": has_link,
        "has_employee_person": emp_row is not None,
        "has_passport_document": pass_doc is not None,
        "has_evaluations": len(evaluations) > 0,
    }

    rule_ids = [str(e["source_rule_id"]) for e in evaluations if e.get("source_rule_id")]
    rc_map = _rule_code_map(conn, rule_ids)

    latest_ts: Optional[str] = None
    for ev in evaluations:
        t = _norm_ts(ev.get("evaluated_at"))
        if t and (latest_ts is None or t > latest_ts):
            latest_ts = t

    status_counts = Counter(
        str((e.get("evaluation_status") or "unknown")).strip() or "unknown" for e in evaluations
    )

    latest_results: List[Dict[str, Any]] = []
    for ev in evaluations:
        rid = ev.get("source_rule_id")
        rc = rc_map.get(str(rid)) if rid is not None else None
        latest_results.append(
            {
                "requirement_code": ev.get("requirement_code"),
                "evaluation_status": ev.get("evaluation_status"),
                "source_rule_code": rc,
                "evaluated_at": _norm_ts(ev.get("evaluated_at")),
            }
        )
    latest_results.sort(key=lambda r: (r.get("evaluated_at") or ""), reverse=True)

    next_actions_preview: Dict[str, Any] = {"actions": []}
    try:
        na = NextActionService().list_actions(conn, cid)
        next_actions_preview = {
            "actions": [
                {
                    "action_title": a.get("action_title"),
                    "priority": a.get("priority"),
                    "related_requirement_code": a.get("related_requirement_code"),
                }
                for a in (na.get("actions") or [])
            ]
        }
    except ProgrammingError as ex:
        log.debug("operational inspect: next actions skipped: %s", ex)

    return {
        "assignment_id": assignment_id,
        "mobility_case_id": cid,
        "bridge_status": bridge_status,
        "readiness_flags": readiness_flags,
        "employee_snapshot": _employee_snapshot(emp_row),
        "passport_document_snapshot": _passport_document_snapshot(pass_doc),
        "latest_evaluation_summary": {
            "evaluated_at": latest_ts,
            "counts_by_status": dict(status_counts),
        },
        "latest_results": latest_results,
        "next_actions_preview": next_actions_preview,
    }


def fetch_audit_logs_for_mobility_case(conn: Connection, case_id: str) -> List[Dict[str, Any]]:
    """Return recent audit rows for the case and its people, documents, evaluations."""
    cid = (case_id or "").strip()
    if not cid:
        return []

    dialect = getattr(conn.engine, "dialect", None)
    if dialect is not None and dialect.name == "postgresql":
        sql = text(
            """
            SELECT
              id::text AS id,
              entity_type,
              entity_id::text AS entity_id,
              action_type,
              old_value_json,
              new_value_json,
              actor_type,
              actor_id::text AS actor_id,
              created_at
            FROM audit_logs
            WHERE entity_id = CAST(:cid AS uuid)
               OR (
                 entity_type = 'case_requirement_evaluations'
                 AND (
                   COALESCE(new_value_json->>'case_id', old_value_json->>'case_id') = :cid_s
                 )
               )
               OR (
                 entity_type = 'case_people'
                 AND (
                   COALESCE(new_value_json->>'case_id', old_value_json->>'case_id') = :cid_s
                 )
               )
               OR (
                 entity_type = 'case_documents'
                 AND (
                   COALESCE(new_value_json->>'case_id', old_value_json->>'case_id') = :cid_s
                 )
               )
            ORDER BY created_at DESC
            LIMIT 500
            """
        )
        params = {"cid": cid, "cid_s": cid}
    else:
        sql = text(
            """
            SELECT id, entity_type, entity_id, action_type,
                   old_value_json, new_value_json, actor_type, actor_id, created_at
            FROM audit_logs
            WHERE entity_id = :cid_s
               OR (
                 entity_type = 'case_requirement_evaluations'
                 AND (
                   (old_value_json IS NOT NULL AND old_value_json LIKE '%' || :cid_s2 || '%')
                   OR (new_value_json IS NOT NULL AND new_value_json LIKE '%' || :cid_s3 || '%')
                 )
               )
            ORDER BY created_at DESC
            LIMIT 500
            """
        )
        params = {"cid_s": cid, "cid_s2": cid, "cid_s3": cid}

    try:
        rows = conn.execute(sql, params).mappings().all()
    except ProgrammingError as ex:
        log.warning("audit_logs query failed (table missing?): %s", ex)
        return []

    import json as _json

    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        for k in ("old_value_json", "new_value_json"):
            v = d.get(k)
            if isinstance(v, dict):
                continue
            if isinstance(v, str) and v.strip().startswith("{"):
                try:
                    d[k] = _json.loads(v)
                except Exception:
                    pass
        if d.get("created_at") is not None and hasattr(d["created_at"], "isoformat"):
            d["created_at"] = d["created_at"].isoformat()
        out.append(d)
    return out
