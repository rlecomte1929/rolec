"""
Sync passport-type case_evidence into graph case_documents (one row per mobility case).

Source of truth remains case_evidence; graph row is a derived index for mobility context / future eval.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

if TYPE_CHECKING:
    from ..database import Database

log = logging.getLogger(__name__)

# Graph document_key aligned with pilot / CaseContext tests (not requirement_code strings).
GRAPH_PASSPORT_DOCUMENT_KEY = "passport_copy"

# Explicit evidence_type values only (no filename heuristics).
_PASSPORT_EVIDENCE_TYPES = frozenset(
    {
        "passport_scan",  # Phase 1 docs example
        "passport_copy",
        "passport",
        "doc_passport",  # HR readiness checklist key
    }
)


def _strip(s: Optional[Any]) -> Optional[str]:
    if s is None:
        return None
    t = str(s).strip()
    return t or None


def _dialect_name(engine: Any) -> str:
    d = getattr(engine, "dialect", None)
    return getattr(d, "name", "") or ""


def _is_passport_evidence_type(evidence_type: Optional[str]) -> bool:
    et = (evidence_type or "").strip().lower()
    return et in _PASSPORT_EVIDENCE_TYPES


def map_case_evidence_status_to_document_status(evidence_status: Optional[str]) -> str:
    """
    case_evidence: submitted | verified | rejected
    case_documents: ... | uploaded | approved | rejected | ...
    """
    s = (evidence_status or "").strip().lower()
    if s == "verified":
        return "approved"
    if s == "rejected":
        return "rejected"
    if s == "submitted":
        return "uploaded"
    return "uploaded"


def _mobility_case_id_for_assignment(conn: Any, assignment_id: str) -> Optional[str]:
    row = conn.execute(
        text(
            "SELECT mobility_case_id FROM assignment_mobility_links "
            "WHERE assignment_id = :aid LIMIT 1"
        ),
        {"aid": assignment_id},
    ).mappings().first()
    if not row:
        return None
    mid = row.get("mobility_case_id")
    return str(mid).strip() if mid is not None else None


def _employee_person_id_for_case(conn: Any, mobility_case_id: str, is_pg: bool) -> Optional[str]:
    row = conn.execute(
        text(
            "SELECT id FROM case_people WHERE case_id = "
            + ("CAST(:cid AS uuid)" if is_pg else ":cid")
            + " AND role = 'employee' ORDER BY created_at ASC, id ASC LIMIT 1"
        ),
        {"cid": mobility_case_id},
    ).mappings().first()
    if not row:
        return None
    return str(row["id"]).strip()


def _pick_newest_passport_evidence(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for r in rows:
        if _is_passport_evidence_type(r.get("evidence_type")):
            return r
    return None


def _build_document_metadata(ev: Dict[str, Any]) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "case_evidence_id": _strip(ev.get("id")),
        "evidence_type": _strip(ev.get("evidence_type")),
        "file_url": _strip(ev.get("file_url")),
        "submitted_at": _strip(ev.get("submitted_at")),
        "requirement_id": _strip(ev.get("requirement_id")),
    }
    raw_meta = ev.get("metadata")
    if isinstance(raw_meta, str) and raw_meta.strip():
        try:
            parsed = json.loads(raw_meta)
            if isinstance(parsed, dict) and parsed:
                meta["evidence_metadata"] = parsed
        except json.JSONDecodeError:
            pass
    elif isinstance(raw_meta, dict) and raw_meta:
        meta["evidence_metadata"] = dict(raw_meta)
    return {k: v for k, v in meta.items() if v is not None}


def ensure_passport_case_document_for_assignment(
    db: "Database",
    assignment_id: str,
    *,
    request_id: Optional[str] = None,
) -> Optional[str]:
    """
    Upsert one case_documents row (document_key=passport_copy) from newest matching case_evidence.

    Returns case_documents.id, or None if no mobility link, no passport evidence, or schema missing.
    Does not delete graph rows when evidence disappears (conservative).
    """
    aid = _strip(assignment_id)
    if not aid:
        return None

    is_pg = _dialect_name(db.engine) == "postgresql"
    now = datetime.utcnow().isoformat()

    try:
        with db.engine.connect() as conn:
            mid = _mobility_case_id_for_assignment(conn, aid)
        if not mid:
            return None

        rows = db.list_assignment_evidence(aid, request_id=request_id)
        ev = _pick_newest_passport_evidence(rows)
        if not ev:
            return None

        doc_status = map_case_evidence_status_to_document_status(ev.get("status"))
        doc_meta = _build_document_metadata(ev)
        meta_json = json.dumps(doc_meta)

        with db.engine.begin() as conn:
            pid = _employee_person_id_for_case(conn, mid, is_pg)

            existing = conn.execute(
                text(
                    "SELECT id FROM case_documents WHERE case_id = "
                    + ("CAST(:cid AS uuid)" if is_pg else ":cid")
                    + " AND document_key = :dk LIMIT 1"
                ),
                {"cid": mid, "dk": GRAPH_PASSPORT_DOCUMENT_KEY},
            ).mappings().first()

            if existing:
                did = str(existing["id"])
                if is_pg:
                    if pid:
                        conn.execute(
                            text(
                                "UPDATE case_documents SET person_id = CAST(:pid AS uuid), "
                                "document_status = :ds, metadata = CAST(:meta AS jsonb), updated_at = NOW() "
                                "WHERE id = CAST(:did AS uuid)"
                            ),
                            {"pid": pid, "ds": doc_status, "meta": meta_json, "did": did},
                        )
                    else:
                        conn.execute(
                            text(
                                "UPDATE case_documents SET person_id = NULL, "
                                "document_status = :ds, metadata = CAST(:meta AS jsonb), updated_at = NOW() "
                                "WHERE id = CAST(:did AS uuid)"
                            ),
                            {"ds": doc_status, "meta": meta_json, "did": did},
                        )
                else:
                    conn.execute(
                        text(
                            "UPDATE case_documents SET person_id = :pid, document_status = :ds, "
                            "metadata = :meta, updated_at = :ua WHERE id = :did"
                        ),
                        {
                            "pid": pid,
                            "ds": doc_status,
                            "meta": meta_json,
                            "did": did,
                            "ua": now,
                        },
                    )
                return did

            did = str(uuid.uuid4())
            try:
                if is_pg:
                    if pid:
                        conn.execute(
                            text(
                                "INSERT INTO case_documents (id, case_id, person_id, document_key, "
                                "document_status, metadata, created_at, updated_at) VALUES ("
                                "CAST(:did AS uuid), CAST(:cid AS uuid), CAST(:pid AS uuid), :dk, :ds, "
                                "CAST(:meta AS jsonb), NOW(), NOW())"
                            ),
                            {
                                "did": did,
                                "cid": mid,
                                "pid": pid,
                                "dk": GRAPH_PASSPORT_DOCUMENT_KEY,
                                "ds": doc_status,
                                "meta": meta_json,
                            },
                        )
                    else:
                        conn.execute(
                            text(
                                "INSERT INTO case_documents (id, case_id, person_id, document_key, "
                                "document_status, metadata, created_at, updated_at) VALUES ("
                                "CAST(:did AS uuid), CAST(:cid AS uuid), NULL, :dk, :ds, "
                                "CAST(:meta AS jsonb), NOW(), NOW())"
                            ),
                            {
                                "did": did,
                                "cid": mid,
                                "dk": GRAPH_PASSPORT_DOCUMENT_KEY,
                                "ds": doc_status,
                                "meta": meta_json,
                            },
                        )
                else:
                    conn.execute(
                        text(
                            "INSERT INTO case_documents (id, case_id, person_id, document_key, "
                            "document_status, metadata, created_at, updated_at) "
                            "VALUES (:did, :cid, :pid, :dk, :ds, :meta, :ca, :ua)"
                        ),
                        {
                            "did": did,
                            "cid": mid,
                            "pid": pid,
                            "dk": GRAPH_PASSPORT_DOCUMENT_KEY,
                            "ds": doc_status,
                            "meta": meta_json,
                            "ca": now,
                            "ua": now,
                        },
                    )
            except IntegrityError:
                row2 = conn.execute(
                    text(
                        "SELECT id FROM case_documents WHERE case_id = "
                        + ("CAST(:cid AS uuid)" if is_pg else ":cid")
                        + " AND document_key = :dk LIMIT 1"
                    ),
                    {"cid": mid, "dk": GRAPH_PASSPORT_DOCUMENT_KEY},
                ).mappings().first()
                if not row2:
                    raise
                did = str(row2["id"])
                if is_pg:
                    if pid:
                        conn.execute(
                            text(
                                "UPDATE case_documents SET person_id = CAST(:pid AS uuid), "
                                "document_status = :ds, metadata = CAST(:meta AS jsonb), updated_at = NOW() "
                                "WHERE id = CAST(:did AS uuid)"
                            ),
                            {"pid": pid, "ds": doc_status, "meta": meta_json, "did": did},
                        )
                    else:
                        conn.execute(
                            text(
                                "UPDATE case_documents SET person_id = NULL, "
                                "document_status = :ds, metadata = CAST(:meta AS jsonb), updated_at = NOW() "
                                "WHERE id = CAST(:did AS uuid)"
                            ),
                            {"ds": doc_status, "meta": meta_json, "did": did},
                        )
                else:
                    conn.execute(
                        text(
                            "UPDATE case_documents SET person_id = :pid, document_status = :ds, "
                            "metadata = :meta, updated_at = :ua WHERE id = :did"
                        ),
                        {
                            "pid": pid,
                            "ds": doc_status,
                            "meta": meta_json,
                            "did": did,
                            "ua": now,
                        },
                    )
            return did
    except (ProgrammingError, OperationalError) as exc:
        log.debug("ensure_passport_case_document_for_assignment failed: %s", exc)
        return None

