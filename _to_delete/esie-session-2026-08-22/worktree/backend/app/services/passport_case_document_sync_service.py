"""
Sync document-type case_evidence into graph case_documents (one row per (case, document_key)).

Source of truth remains case_evidence; the graph row is a derived index for mobility
context / future eval. Originally passport-only; generalized so any roadmap document key
(passport_copy, employment_letter, spouse_passport_copy, income_proof, …) gets the same
upsert treatment via ``ensure_case_document_for_key``. ``ensure_passport_case_document_for_assignment``
is preserved as a thin wrapper so existing callers keep working unchanged.
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
    from ...database import Database

log = logging.getLogger(__name__)

# Graph document_key aligned with pilot / CaseContext tests (not requirement_code strings).
GRAPH_PASSPORT_DOCUMENT_KEY = "passport_copy"

# ---------------------------------------------------------------------------
# Evidence-type → canonical document_key registry.
#
# Canonical keys map 1:1 to themselves (identity). Aliases (legacy / source-system
# spellings) fold into their canonical key. Anything NOT listed here is treated as a
# canonical key in its own right (identity fallback), so a brand-new document_key
# uploaded directly through the case-documents endpoint (evidence_type == document_key)
# still matches itself without needing a registry entry.
# ---------------------------------------------------------------------------
EVIDENCE_TYPE_TO_DOCUMENT_KEY: Dict[str, str] = {
    # passport (canonical + aliases) — preserves the original passport set.
    "passport_copy": "passport_copy",
    "passport_scan": "passport_copy",
    "passport": "passport_copy",
    "doc_passport": "passport_copy",
    # employment / assignment letter.
    "employment_letter": "employment_letter",
    "employment_contract": "employment_letter",
    "signed_employment_contract": "employment_letter",
    "assignment_letter": "employment_letter",
    "doc_employment_letter": "employment_letter",
    # spouse / dependant identity.
    "spouse_passport_copy": "spouse_passport_copy",
    "spouse_passport": "spouse_passport_copy",
    # relationship proof.
    "marriage_or_partnership_cert": "marriage_or_partnership_cert",
    "marriage_certificate": "marriage_or_partnership_cert",
    "partnership_certificate": "marriage_or_partnership_cert",
    # finances.
    "income_proof": "income_proof",
    "proof_of_income": "income_proof",
    # housing.
    "accommodation_proof_nl": "accommodation_proof_nl",
    "accommodation_proof": "accommodation_proof_nl",
    # schooling.
    "previous_school_reports": "previous_school_reports",
    "school_reports": "previous_school_reports",
}


def _strip(s: Optional[Any]) -> Optional[str]:
    if s is None:
        return None
    t = str(s).strip()
    return t or None


def _dialect_name(engine: Any) -> str:
    d = getattr(engine, "dialect", None)
    return getattr(d, "name", "") or ""


def document_key_for_evidence_type(evidence_type: Optional[str]) -> Optional[str]:
    """Resolve an evidence_type to its canonical document_key.

    Known aliases fold into their canonical key; unknown values are treated as
    canonical in their own right (identity). Empty/None → None.
    """
    et = (evidence_type or "").strip().lower()
    if not et:
        return None
    return EVIDENCE_TYPE_TO_DOCUMENT_KEY.get(et, et)


def _evidence_matches_document_key(evidence_type: Optional[str], document_key: str) -> bool:
    return document_key_for_evidence_type(evidence_type) == document_key


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


def _pick_newest_evidence_for_key(
    rows: List[Dict[str, Any]], document_key: str
) -> Optional[Dict[str, Any]]:
    """Rows are newest-first (list_assignment_evidence orders created_at DESC)."""
    for r in rows:
        if _evidence_matches_document_key(r.get("evidence_type"), document_key):
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


def ensure_case_document_for_key(
    db: "Database",
    assignment_id: str,
    document_key: str,
    *,
    request_id: Optional[str] = None,
) -> Optional[str]:
    """
    Upsert one case_documents row (for ``document_key``) from the newest matching
    case_evidence (evidence_type that maps to ``document_key``).

    Returns case_documents.id, or None if no mobility link, no matching evidence, or
    schema missing. Does not delete graph rows when evidence disappears (conservative).

    Unique (case_id, document_key): repeated calls update the same row in place.
    """
    aid = _strip(assignment_id)
    dk = _strip(document_key)
    if not aid or not dk:
        return None

    is_pg = _dialect_name(db.engine) == "postgresql"
    now = datetime.utcnow().isoformat()

    try:
        with db.engine.connect() as conn:
            mid = _mobility_case_id_for_assignment(conn, aid)
        if not mid:
            return None

        rows = db.list_assignment_evidence(aid, request_id=request_id)
        ev = _pick_newest_evidence_for_key(rows, dk)
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
                {"cid": mid, "dk": dk},
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
                                "dk": dk,
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
                                "dk": dk,
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
                            "dk": dk,
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
                    {"cid": mid, "dk": dk},
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
        log.debug("ensure_case_document_for_key(%s) failed: %s", document_key, exc)
        return None


def ensure_passport_case_document_for_assignment(
    db: "Database",
    assignment_id: str,
    *,
    request_id: Optional[str] = None,
) -> Optional[str]:
    """Thin wrapper — preserves the original passport-only call shape.

    Existing callers (backend/main.py add_assignment_evidence) keep working; this
    now just delegates to the generic upsert with ``passport_copy``.
    """
    return ensure_case_document_for_key(
        db, assignment_id, GRAPH_PASSPORT_DOCUMENT_KEY, request_id=request_id
    )
