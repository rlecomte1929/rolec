"""
PolicyAssistantContext read model: case + active snapshot + filtered facts + source chunks.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import text

from ..database import Database
from .case_context_service import CaseContextError, CaseContextService
from .policy_applicability_engine import detect_fact_conflicts, evaluate_fact_applicability


def _strip(s: Any) -> Optional[str]:
    if s is None:
        return None
    t = str(s).strip()
    return t or None


def _parse_case_id(case_id: str) -> Optional[str]:
    t = _strip(case_id)
    if not t:
        return None
    try:
        return str(uuid.UUID(t))
    except Exception:
        return None


def _family_summary(people: List[Dict[str, Any]]) -> Dict[str, Any]:
    roles = {str(p.get("role") or "") for p in people}
    has_spouse = "spouse_partner" in roles
    has_dep = "dependent" in roles
    return {
        "has_accompanying_spouse": has_spouse,
        "has_dependents": has_dep,
        "roles": sorted(roles),
    }


def _case_assignment_type(case_row: Optional[Dict[str, Any]]) -> Optional[str]:
    if not case_row:
        return None
    ct = case_row.get("case_type")
    if ct:
        return str(ct).strip().lower() or None
    meta = case_row.get("metadata") if isinstance(case_row.get("metadata"), dict) else {}
    at = meta.get("assignment_type") or meta.get("assignmentType")
    if at:
        return str(at).strip().lower() or None
    return None


def fact_applies_to_case_profile(fact: Dict[str, Any], profile: Dict[str, Any]) -> bool:
    """
    Conservative filter: if applicability is empty, include.
    If assignment_types is set, require overlap with case assignment type when known.
    """
    app = fact.get("applicability_json") or {}
    if not isinstance(app, dict):
        return True
    req_at = app.get("assignment_types")
    case_at = profile.get("assignment_type")
    if isinstance(req_at, list) and req_at and case_at:
        norm = {str(x).strip().lower() for x in req_at}
        if case_at not in norm:
            return False
    # Destination / origin: only filter when both sides specify ISO-like hints (future extension).
    return True


def get_policy_facts_for_case(
    db: Database,
    case_id: str,
    *,
    fact_types: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Resolve active snapshot for case company and return filtered facts + profile."""
    cid = _parse_case_id(case_id)
    if not cid:
        return {"ok": False, "error": "invalid_case_id", "facts": [], "case_profile": {}}

    if not db.policy_assistant_tables_available():
        return {
            "ok": True,
            "policy_knowledge_available": False,
            "message": "no uploaded policy knowledge available",
            "facts": [],
            "case_profile": {},
        }

    try:
        with db.engine.connect() as conn:
            ctx = CaseContextService().fetch(conn, cid)
    except CaseContextError:
        return {
            "ok": True,
            "policy_knowledge_available": False,
            "message": "no uploaded policy knowledge available",
            "facts": [],
            "case_profile": {},
        }

    if not ctx.get("meta", {}).get("case_found"):
        return {"ok": False, "error": "case_not_found", "facts": [], "case_profile": {}}

    case_row = ctx.get("case") or {}
    company_id = _strip(case_row.get("company_id"))
    if not company_id:
        return {"ok": False, "error": "case_missing_company", "facts": [], "case_profile": {}}

    snap = db.get_active_policy_knowledge_snapshot_for_company(company_id)
    if not snap:
        return {
            "ok": True,
            "policy_knowledge_available": False,
            "message": "no uploaded policy knowledge available",
            "company_id": company_id,
            "case_id": cid,
            "facts": [],
            "case_profile": _build_case_profile(cid, case_row, ctx.get("people") or []),
        }

    snapshot_id = str(snap.get("id"))
    doc_id = str(snap.get("policy_document_id"))
    raw_facts = db.list_policy_facts_for_snapshot(snapshot_id)
    profile = _build_case_profile(cid, case_row, ctx.get("people") or [])

    enriched: List[Dict[str, Any]] = []
    for f in raw_facts:
        ft = str(f.get("fact_type") or "")
        if fact_types and ft not in fact_types:
            continue
        ev = evaluate_fact_applicability(f, profile)
        row = dict(f)
        row["applicability_decision"] = ev
        enriched.append(row)

    applicable_only = [
        x
        for x in enriched
        if (x.get("applicability_decision") or {}).get("applicability_status") == "applicable"
    ]
    conflicts = detect_fact_conflicts(applicable_only)

    return {
        "ok": True,
        "policy_knowledge_available": True,
        "company_id": company_id,
        "case_id": cid,
        "snapshot_id": snapshot_id,
        "document_id": doc_id,
        "facts": applicable_only,
        "all_facts_enriched": enriched,
        "all_facts_count": len(raw_facts),
        "filtered_facts_count": len(applicable_only),
        "case_profile": profile,
        "fact_conflicts": conflicts,
        "partial_extraction_hints": {
            "ambiguous_facts": sum(1 for x in enriched if x.get("ambiguity_flag")),
            "cannot_determine_case": sum(
                1
                for x in enriched
                if (x.get("applicability_decision") or {}).get("applicability_status")
                == "cannot_determine_missing_case_data"
            ),
            "cannot_determine_policy": sum(
                1
                for x in enriched
                if (x.get("applicability_decision") or {}).get("applicability_status")
                == "cannot_determine_policy_ambiguity"
            ),
        },
    }


def _build_case_profile(
    case_id: str,
    case_row: Dict[str, Any],
    people: List[Dict[str, Any]],
) -> Dict[str, Any]:
    fam = _family_summary(people)
    return {
        "case_id": case_id,
        "company_id": _strip(case_row.get("company_id")),
        "assignment_type": _case_assignment_type(case_row),
        "origin_country": _strip(case_row.get("origin_country")),
        "destination_country": _strip(case_row.get("destination_country")),
        "family": fam,
        "metadata": case_row.get("metadata") if isinstance(case_row.get("metadata"), dict) else {},
    }


def get_source_chunks_for_fact_ids(db: Database, fact_ids: List[str]) -> List[Dict[str, Any]]:
    if not fact_ids or not db.policy_assistant_tables_available():
        return []
    chunk_ids: List[str] = []
    with db.engine.connect() as conn:
        placeholders = ",".join([f":f{i}" for i in range(len(fact_ids))])
        params = {f"f{i}": fact_ids[i] for i in range(len(fact_ids))}
        rows = conn.execute(
            text(f"SELECT source_chunk_id FROM policy_facts WHERE id IN ({placeholders})"),
            params,
        ).fetchall()
        for r in rows:
            m = dict(r._mapping) if hasattr(r, "_mapping") else dict(r)
            sc = m.get("source_chunk_id")
            if sc:
                chunk_ids.append(str(sc))
    return db.get_policy_document_chunks_by_ids(list(dict.fromkeys(chunk_ids)))


def build_policy_assistant_context(db: Database, case_id: str) -> Dict[str, Any]:
    """PolicyAssistantContext payload for GET /api/policy-assistant/cases/{case_id}/context"""
    res = get_policy_facts_for_case(db, case_id)
    if not res.get("ok"):
        return {
            "company_id": None,
            "case_id": _parse_case_id(case_id),
            "snapshot_id": None,
            "document_id": None,
            "case_profile": res.get("case_profile") or {},
            "applicable_facts": [],
            "supporting_chunks": [],
            "policy_knowledge_available": False,
            "message": res.get("error") or "unable_to_resolve_case",
        }

    if not res.get("policy_knowledge_available"):
        return {
            "company_id": res.get("company_id"),
            "case_id": res.get("case_id"),
            "snapshot_id": None,
            "document_id": None,
            "case_profile": res.get("case_profile") or {},
            "applicable_facts": [],
            "supporting_chunks": [],
            "policy_knowledge_available": False,
            "message": res.get("message") or "no uploaded policy knowledge available",
        }

    facts: List[Dict[str, Any]] = list(res.get("facts") or [])
    fact_conflicts = res.get("fact_conflicts") or []
    chunk_ids = list(
        dict.fromkeys(str(f["source_chunk_id"]) for f in facts if f.get("source_chunk_id"))
    )
    chunks = db.get_policy_document_chunks_by_ids(chunk_ids)

    # Public fact shape (include traceability)
    pub_facts: List[Dict[str, Any]] = []
    for f in facts:
        pub_facts.append(
            {
                "id": f.get("id"),
                "fact_type": f.get("fact_type"),
                "category": f.get("category"),
                "subcategory": f.get("subcategory"),
                "normalized_value_json": f.get("normalized_value_json") or {},
                "applicability_json": f.get("applicability_json") or {},
                "ambiguity_flag": bool(f.get("ambiguity_flag")),
                "confidence_score": f.get("confidence_score"),
                "source_chunk_id": f.get("source_chunk_id"),
                "source_page": f.get("source_page"),
                "source_section": f.get("source_section"),
                "source_quote": f.get("source_quote"),
                "applicability_decision": f.get("applicability_decision") or {},
            }
        )

    pub_chunks: List[Dict[str, Any]] = []
    for c in chunks:
        pub_chunks.append(
            {
                "id": c.get("id"),
                "chunk_index": c.get("chunk_index"),
                "page_number": c.get("page_number"),
                "section_title": c.get("section_title"),
                "text_content": c.get("text_content"),
                "metadata_json": c.get("metadata_json") or {},
            }
        )

    return {
        "company_id": res.get("company_id"),
        "case_id": res.get("case_id"),
        "snapshot_id": res.get("snapshot_id"),
        "document_id": res.get("document_id"),
        "case_profile": res.get("case_profile") or {},
        "applicable_facts": pub_facts,
        "supporting_chunks": pub_chunks,
        "policy_knowledge_available": True,
        "partial_extraction": res.get("partial_extraction_hints") or {},
        "fact_conflicts": fact_conflicts,
    }
