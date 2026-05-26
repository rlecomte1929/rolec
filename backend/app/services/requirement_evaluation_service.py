"""
RequirementEvaluationService — deterministic MVP evaluator (no AI).

Uses CaseContextService snapshot, maps policy rule requirement codes to catalog rows,
checks case_documents with a small keyword map, upserts case_requirement_evaluations
for evaluated_by='system' (same natural key = update in place, preserves id/history id stable).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import ProgrammingError

from .audit_log_service import (
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_SYSTEM,
    fetch_evaluation_row_dict,
    insert_audit_log,
)
from .case_context_service import CaseContextError, CaseContextService

log = logging.getLogger(__name__)

EVALUATED_BY_SYSTEM = "system"

# MVP: requirement_code -> how we look for a supporting document (substring match on document_key)
_REQUIREMENT_DOC_PROFILE: Dict[str, Dict[str, Any]] = {
    "passport_valid": {
        "keywords": ["passport"],
        "when_present": "needs_review",
        "reason_present": "Passport document is on file; expiry/validity is not checked automatically (MVP).",
        "reason_missing": "No passport document found for this person on the case.",
    },
    "passport_copy_uploaded": {
        "keywords": ["passport"],
        "when_present": "met",
        "when_rejected": "needs_review",
        "reason_present": "Passport copy is uploaded and marked as on file.",
        "reason_rejected": "A passport file exists but was rejected — please re-upload or contact HR.",
        "reason_missing": "Passport copy has not been uploaded yet.",
    },
    "signed_employment_contract": {
        "keywords": ["contract", "employment"],
        "when_present": "met",
        "when_rejected": "needs_review",
        "reason_present": "Employment contract document is on file.",
        "reason_rejected": "Contract document was rejected — needs a new upload or HR review.",
        "reason_missing": "Signed employment contract is not on file yet.",
    },
    "proof_of_address": {
        "keywords": ["address", "proof_of_address", "residence"],
        "when_present": "met",
        "when_rejected": "needs_review",
        "reason_present": "Proof of address document is on file.",
        "reason_rejected": "Proof of address was rejected — please provide an updated document.",
        "reason_missing": "Proof of address has not been provided yet.",
    },
}

_MET_DOC_STATUSES = frozenset({"uploaded", "under_review", "approved"})
_MISSING_DOC_STATUSES = frozenset({"missing", "requested"})
_REJECT_DOC_STATUSES = frozenset({"rejected"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _doc_matches_keywords(doc_key: Optional[str], keywords: List[str]) -> bool:
    dk = _norm(doc_key)
    if not dk:
        return False
    return any(kw.lower() in dk for kw in keywords)


def _filter_docs_for_person(
    documents: List[Dict[str, Any]],
    person_id: Optional[str],
) -> List[Dict[str, Any]]:
    """Include case-level docs (no person_id) plus docs owned by the subject person."""
    if person_id is None:
        return [d for d in documents if d.get("person_id") in (None, "")]
    out: List[Dict[str, Any]] = []
    for d in documents:
        pid = d.get("person_id")
        if pid in (None, ""):
            out.append(d)
        elif str(pid) == str(person_id):
            out.append(d)
    return out


def _pick_best_doc_for_requirement(
    documents: List[Dict[str, Any]],
    keywords: List[str],
) -> Optional[Dict[str, Any]]:
    matches = [d for d in documents if _doc_matches_keywords(d.get("document_key"), keywords)]
    if not matches:
        return None
    priority = {"approved": 3, "under_review": 2, "uploaded": 2, "requested": 1, "missing": 0, "rejected": 0, "waived": 0}
    matches.sort(
        key=lambda d: priority.get(_norm(d.get("document_status")), 0),
        reverse=True,
    )
    return matches[0]


def _evaluate_one_requirement(
    requirement_code: str,
    documents: List[Dict[str, Any]],
) -> Tuple[str, str]:
    """
    Returns (evaluation_status, reason_text) using MVP vocabulary only.
    """
    code = _norm(requirement_code)
    profile = _REQUIREMENT_DOC_PROFILE.get(requirement_code) or _REQUIREMENT_DOC_PROFILE.get(code)
    if not profile:
        return (
            "needs_review",
            f"No automated document mapping for requirement '{requirement_code}' (MVP).",
        )

    keywords = profile.get("keywords") or []
    doc = _pick_best_doc_for_requirement(documents, keywords)
    if doc is None:
        return "missing", str(profile.get("reason_missing") or "Required document not found.")

    st = _norm(doc.get("document_status"))
    if st in _REJECT_DOC_STATUSES:
        when_rej = profile.get("when_rejected")
        if when_rej == "needs_review":
            return "needs_review", str(profile.get("reason_rejected") or "Document needs review.")
        return "missing", str(profile.get("reason_rejected") or "Document rejected.")

    if st in _MET_DOC_STATUSES:
        when_present = profile.get("when_present", "met")
        return str(when_present), str(profile.get("reason_present") or "Requirement satisfied based on document status.")

    if st in _MISSING_DOC_STATUSES:
        return "missing", str(profile.get("reason_missing") or "Document not yet provided.")

    if st == "waived":
        return "not_applicable", "This document requirement was waived for the case."

    return "needs_review", f"Document '{doc.get('document_key')}' has status '{st}' — needs human review (MVP)."


def _first_person_for_roles(people: List[Dict[str, Any]], roles: List[str]) -> Optional[str]:
    allowed = {_norm(r) for r in roles}
    if not allowed:
        for p in people:
            pid = p.get("id")
            if pid:
                return str(pid)
        return None
    for p in people:
        if _norm(p.get("role")) in allowed:
            pid = p.get("id")
            if pid:
                return str(pid)
    return None


def _req_id_for_code(requirements: List[Dict[str, Any]], code: str) -> Optional[str]:
    c = _norm(code)
    for r in requirements:
        if _norm(r.get("requirement_code")) == c:
            rid = r.get("id")
            return str(rid) if rid else None
    return None


def _audit_evaluation_write(
    conn: Connection,
    evaluation_id: str,
    action_type: str,
    old_row: Optional[Dict[str, Any]],
    new_row: Optional[Dict[str, Any]],
) -> None:
    try:
        insert_audit_log(
            conn,
            entity_type="case_requirement_evaluations",
            entity_id=evaluation_id,
            action_type=action_type,
            old_value=old_row,
            new_value=new_row,
            actor_type=ACTOR_SYSTEM,
            actor_id=None,
        )
    except Exception as ex:
        log.warning("audit_logs insert skipped (table missing or DB error): %s", ex)


def _find_existing_evaluation_id(
    conn: Connection,
    case_id: str,
    requirement_id: str,
    source_rule_id: str,
    person_id: Optional[str],
    evaluated_by: str,
) -> Optional[str]:
    """Match natural key for system rows (same case/rule/requirement/person bucket)."""
    pid_key = person_id or ""
    rid_key = source_rule_id or ""
    row = conn.execute(
        text(
            """
            SELECT id
            FROM case_requirement_evaluations
            WHERE case_id = :case_id
              AND requirement_id = :requirement_id
              AND evaluated_by = :evaluated_by
              AND coalesce(cast(source_rule_id as text), '') = :sr_key
              AND coalesce(cast(person_id as text), '') = :p_key
            LIMIT 1
            """
        ),
        {
            "case_id": case_id,
            "requirement_id": requirement_id,
            "evaluated_by": evaluated_by,
            "sr_key": rid_key,
            "p_key": pid_key,
        },
    ).mappings().first()
    if not row:
        return None
    i = row.get("id")
    return str(i) if i is not None else None


def _upsert_evaluation(
    conn: Connection,
    case_id: str,
    person_id: Optional[str],
    requirement_id: str,
    source_rule_id: str,
    evaluation_status: str,
    reason_text: str,
    evaluated_at: datetime,
) -> str:
    eid = _find_existing_evaluation_id(
        conn, case_id, requirement_id, source_rule_id, person_id, EVALUATED_BY_SYSTEM
    )
    rtxt = (reason_text or "")[:4000]
    if eid:
        old_row = fetch_evaluation_row_dict(conn, eid)
        conn.execute(
            text(
                """
                UPDATE case_requirement_evaluations
                SET evaluation_status = :st,
                    reason_text = :rt,
                    evaluated_at = :ea,
                    updated_at = :ua,
                    person_id = :pid
                WHERE id = :id
                """
            ),
            {
                "st": evaluation_status,
                "rt": rtxt,
                "ea": evaluated_at,
                "ua": evaluated_at,
                "pid": person_id,
                "id": eid,
            },
        )
        new_row = fetch_evaluation_row_dict(conn, eid)
        _audit_evaluation_write(conn, eid, ACTION_UPDATE, old_row, new_row)
        return eid
    new_id = str(uuid.uuid4())
    conn.execute(
        text(
            """
            INSERT INTO case_requirement_evaluations (
              id, case_id, person_id, requirement_id, source_rule_id,
              evaluation_status, reason_text, evaluated_at, evaluated_by,
              created_at, updated_at
            ) VALUES (
              :id, :case_id, :person_id, :requirement_id, :source_rule_id,
              :st, :rt, :ea, :eb,
              :ca, :ua
            )
            """
        ),
        {
            "id": new_id,
            "case_id": case_id,
            "person_id": person_id,
            "requirement_id": requirement_id,
            "source_rule_id": source_rule_id or None,
            "st": evaluation_status,
            "rt": rtxt,
            "ea": evaluated_at,
            "eb": EVALUATED_BY_SYSTEM,
            "ca": evaluated_at,
            "ua": evaluated_at,
        },
    )
    inserted = fetch_evaluation_row_dict(conn, new_id)
    _audit_evaluation_write(conn, new_id, ACTION_INSERT, None, inserted)
    return new_id


class RequirementEvaluationService:
    def evaluate_case(self, conn: Connection, case_id_raw: Optional[str]) -> Dict[str, Any]:
        evaluated_at = _utc_now()
        ctx = CaseContextService().fetch(conn, case_id_raw)
        meta = ctx.get("meta") or {}

        out: Dict[str, Any] = {
            "meta": {
                "ok": bool(meta.get("ok")),
                "case_id": meta.get("case_id"),
                "case_found": bool(meta.get("case_found")),
                "evaluated_at": evaluated_at.isoformat(),
                "evaluated_by": EVALUATED_BY_SYSTEM,
            },
            "results": [],
            "error": None,
        }

        if not meta.get("ok"):
            out["meta"]["ok"] = False
            out["error"] = meta.get("error") or {"code": "invalid_case_id", "message": "Invalid case id"}
            return out

        if not meta.get("case_found"):
            out["error"] = {"code": "case_not_found", "message": "Mobility case not found"}
            return out

        case_id = str((ctx.get("case") or {}).get("id"))
        people: List[Dict[str, Any]] = list(ctx.get("people") or [])
        documents: List[Dict[str, Any]] = list(ctx.get("documents") or [])
        applicable_rules: List[Dict[str, Any]] = list(ctx.get("applicable_rules") or [])
        requirements: List[Dict[str, Any]] = list(ctx.get("requirements") or [])

        results: List[Dict[str, Any]] = []

        try:
            for rule in applicable_rules:
                rule_id = rule.get("id")
                if not rule_id:
                    continue
                cond = rule.get("conditions")
                if not isinstance(cond, dict):
                    continue
                codes = cond.get("requires_requirement_codes")
                if not isinstance(codes, list):
                    continue
                applies_roles = cond.get("applies_to_roles")
                roles_list = applies_roles if isinstance(applies_roles, list) else []
                subject_person_id = _first_person_for_roles(people, [str(r) for r in roles_list])

                doc_scope = _filter_docs_for_person(documents, subject_person_id)

                for code in codes:
                    if code is None:
                        continue
                    cstr = str(code).strip()
                    if not cstr:
                        continue
                    req_id = _req_id_for_code(requirements, cstr)
                    if not req_id:
                        log.warning("Requirement code %s not in catalog snapshot for case %s", cstr, case_id)
                        continue

                    st, reason = _evaluate_one_requirement(cstr, doc_scope)
                    eid = _upsert_evaluation(
                        conn,
                        case_id=case_id,
                        person_id=subject_person_id,
                        requirement_id=req_id,
                        source_rule_id=str(rule_id),
                        evaluation_status=st,
                        reason_text=reason,
                        evaluated_at=evaluated_at,
                    )
                    results.append(
                        {
                            "evaluation_id": eid,
                            "requirement_code": cstr,
                            "requirement_id": req_id,
                            "source_rule_id": str(rule_id),
                            "source_rule_code": rule.get("rule_code"),
                            "person_id": subject_person_id,
                            "evaluation_status": st,
                            "reason_text": reason,
                        }
                    )
        except ProgrammingError as ex:
            log.warning("RequirementEvaluationService: write failed: %s", ex)
            raise CaseContextError(
                "mobility_schema_unavailable",
                "case_requirement_evaluations table missing required columns (apply migrations).",
            ) from ex

        out["results"] = results
        out["meta"]["evaluated_count"] = len(results)
        return out


def evaluate_case_requirements(conn: Connection, case_id_raw: Optional[str]) -> Dict[str, Any]:
    return RequirementEvaluationService().evaluate_case(conn, case_id_raw)
