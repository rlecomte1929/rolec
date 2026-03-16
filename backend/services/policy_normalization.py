"""
Policy normalization engine: maps policy_document_clauses into canonical policy objects.

Pipeline stage (3-stage model):
- Ingest (upload): store file, extract raw text and metadata, segment clauses. See policy_document_intake + main upload.
- Reprocess: re-run extraction and clause segmentation from stored file. See main reprocess endpoint.
- Normalize: transform extracted clauses into structured policy objects, policy_version, benefit_rules, exclusions,
  evidence_requirements, conditions, and source_links. This module implements the normalize stage.
  Normalize is separate so HR can re-segment (reprocess) without overwriting structured edits, and so we can
  re-normalize after taxonomy or rule changes while keeping the same policy versioning model.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from .policy_taxonomy import (
    BENEFIT_TAXONOMY,
    ASSIGNMENT_TYPE_MAP,
    FAMILY_STATUS_MAP,
    POLICY_THEMES,
    resolve_benefit_key,
    get_benefit_meta,
    resolve_theme,
)

log = logging.getLogger(__name__)

# calc_type detection patterns
CALC_PERCENT = re.compile(r"(\d{1,3})\s*%\s*(?:of|on)?\s*(?:base\s+)?salary", re.I)
CALC_DAYS = re.compile(r"(\d{1,4})\s*(?:days?|working\s+days?)", re.I)
CALC_DIFFERENCE = re.compile(r"difference|reimburse.*difference|difference\s+only", re.I)
CALC_PER_DIEM = re.compile(r"per\s+diem|daily\s+(?:rate|allowance)", re.I)


def _detect_calc_type(raw_text: str, hints: Dict[str, Any], benefit_key: str) -> str:
    """Infer calc_type from text and hints."""
    lower = raw_text.lower()
    meta = get_benefit_meta(benefit_key)
    default = meta.get("default_calc_type", "other")

    if CALC_PERCENT.search(raw_text):
        return "percent_salary"
    if "%" in lower and "salary" in lower:
        return "percent_salary"
    if hints.get("candidate_unit") == "%":
        return "percent_salary"

    if CALC_DAYS.search(raw_text):
        return "unit_cap"
    if hints.get("candidate_unit") in ("days", "weeks", "months"):
        return "unit_cap"

    if CALC_DIFFERENCE.search(raw_text):
        return "difference_only"
    if "reimburse" in lower or "reimbursed" in lower:
        if "difference" in lower or "school" in lower or "tuition" in lower:
            return "difference_only"
        return "reimbursement"

    if CALC_PER_DIEM.search(raw_text):
        return "per_diem"

    if hints.get("candidate_numeric_values") and hints.get("candidate_currency"):
        return "flat_amount"

    return default


def _extract_amount_value(hints: Dict[str, Any], raw_text: str) -> Optional[float]:
    """Extract primary numeric value from hints or text."""
    nums = hints.get("candidate_numeric_values") or []
    if nums:
        return float(nums[0])
    m = re.search(r"(?:\b|\$|€|£)\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)", raw_text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    m = re.search(r"(\d{1,3})\s*%", raw_text)
    if m:
        return float(m.group(1))
    return None


def _normalize_assignment_types(hints: Dict[str, Any]) -> List[str]:
    """Normalize assignment types from hints."""
    ats = hints.get("candidate_assignment_types") or []
    result = []
    for a in ats:
        key = str(a).lower().replace("-", "_")
        mapped = ASSIGNMENT_TYPE_MAP.get(key)
        if mapped and mapped not in result:
            result.append(mapped)
    return result


def _normalize_family_status(hints: Dict[str, Any]) -> List[str]:
    """Normalize family status terms from hints."""
    fts = hints.get("candidate_family_status_terms") or []
    result = []
    for f in fts:
        key = str(f).lower()
        mapped = FAMILY_STATUS_MAP.get(key)
        if mapped and mapped not in result:
            result.append(mapped)
    return result


def normalize_clauses_to_objects(
    clauses: List[Dict[str, Any]], doc_id: str
) -> Dict[str, Any]:
    """
    Convert policy_document_clauses into canonical objects.
    Returns dict with benefit_rules, exclusions, evidence_requirements, conditions,
    assignment_applicability, family_applicability, source_links.
    """
    benefit_rules: List[Dict[str, Any]] = []
    exclusions: List[Dict[str, Any]] = []
    evidence_requirements: List[Dict[str, Any]] = []
    conditions: List[Dict[str, Any]] = []
    assignment_applicability: List[Dict[str, Any]] = []  # (benefit_rule_id, assignment_type)
    family_applicability: List[Dict[str, Any]] = []
    source_links: List[Dict[str, Any]] = []

    benefit_rule_ids: Dict[int, str] = {}  # clause index -> rule id (temp, set after insert)

    for i, clause in enumerate(clauses):
        cid = clause.get("id")
        raw = clause.get("raw_text") or ""
        ctype = clause.get("clause_type", "unknown")
        hints = clause.get("normalized_hint_json") or {}
        section = clause.get("section_label")
        page_start = clause.get("source_page_start")
        page_end = clause.get("source_page_end")
        anchor = clause.get("source_anchor")
        conf = clause.get("confidence", 0.5)

        def add_source(obj_type: str, obj_id: str) -> None:
            source_links.append({
                "object_type": obj_type,
                "object_id": obj_id,
                "clause_id": cid,
                "source_page_start": page_start,
                "source_page_end": page_end,
                "source_anchor": anchor,
            })

        # Benefits
        benefit_key = resolve_benefit_key(
            hints.get("candidate_benefit_key"),
            section,
            raw,
        )
        if benefit_key and ctype in ("benefit", "tax_rule", "unknown"):
            if ctype == "exclusion":
                continue  # handle below
            meta = get_benefit_meta(benefit_key)
            theme = resolve_theme(benefit_key, meta.get("group"))
            calc_type = _detect_calc_type(raw, hints, benefit_key)
            amount_value = _extract_amount_value(hints, raw)
            amount_unit = hints.get("candidate_unit")
            currency = hints.get("candidate_currency")
            frequency = hints.get("candidate_frequency") or "per_assignment"

            rule = {
                "benefit_key": benefit_key,
                "benefit_category": theme,
                "calc_type": calc_type,
                "amount_value": amount_value,
                "amount_unit": amount_unit,
                "currency": currency,
                "frequency": frequency,
                "description": raw[:500],
                "metadata_json": {},
                "auto_generated": True,
                "review_status": "pending",
                "confidence": conf,
                "raw_text": raw[:2000],
                "_clause_idx": i,
                "_clause_id": cid,
            }
            if calc_type == "difference_only" and benefit_key == "schooling":
                rule["metadata_json"] = {"reimbursement_logic": "difference_only"}
            benefit_rules.append(rule)

            ats = _normalize_assignment_types(hints)
            for at in ats:
                assignment_applicability.append({
                    "_benefit_clause_idx": i,
                    "assignment_type": at,
                })
            fts = _normalize_family_status(hints)
            for fs in fts:
                family_applicability.append({
                    "_benefit_clause_idx": i,
                    "family_status": fs,
                })

        # Exclusions
        if ctype == "exclusion" or hints.get("candidate_exclusion_flag"):
            domain = "scope"
            if any(s in raw.lower() for s in ["tax", "tax equalization", "hypothetical"]):
                domain = "tax"
            if benefit_key:
                domain = "benefit"
            exclusions.append({
                "benefit_key": benefit_key if domain == "benefit" else None,
                "domain": domain,
                "description": raw[:500],
                "auto_generated": True,
                "review_status": "pending",
                "confidence": conf,
                "raw_text": raw[:2000],
                "_clause_id": cid,
            })

        # Evidence requirements
        if ctype == "evidence_rule" or hints.get("candidate_evidence_items"):
            items = hints.get("candidate_evidence_items") or []
            if not items and "receipt" in raw.lower():
                items = ["receipts"]
            if items:
                evidence_requirements.append({
                    "benefit_rule_id": None,  # link later if we have benefit from same section
                    "evidence_items_json": items,
                    "description": raw[:300],
                    "auto_generated": True,
                    "review_status": "pending",
                    "confidence": conf,
                    "raw_text": raw[:2000],
                    "_clause_id": cid,
                })

        # Conditions (assignment_type, family_status, duration_threshold)
        ats = _normalize_assignment_types(hints)
        if ats:
            for at in ats:
                conditions.append({
                    "object_type": "benefit_rule",
                    "object_id": None,  # set when we have benefit_rule_id
                    "condition_type": "assignment_type",
                    "condition_value_json": {"types": [at]},
                    "auto_generated": True,
                    "review_status": "pending",
                    "confidence": conf,
                    "_benefit_clause_idx": i,
                    "_clause_id": cid,
                })
        fts = _normalize_family_status(hints)
        if fts:
            for fs in fts:
                conditions.append({
                    "object_type": "benefit_rule",
                    "object_id": None,
                    "condition_type": "family_status",
                    "condition_value_json": {"statuses": [fs]},
                    "auto_generated": True,
                    "review_status": "pending",
                    "confidence": conf,
                    "_benefit_clause_idx": i,
                    "_clause_id": cid,
                })

        # Duration threshold
        m = re.search(r"(\d{1,3})\s*(?:months?|years?)", raw, re.I)
        if m and any(w in raw.lower() for w in ["assignment", "duration", "longer than", "exceeds"]):
            val = int(m.group(1))
            if "year" in m.group(0).lower():
                val = val * 12
            conditions.append({
                "object_type": "benefit_rule",
                "object_id": None,
                "condition_type": "duration_threshold",
                "condition_value_json": {"min_months": val},
                "auto_generated": True,
                "review_status": "pending",
                "confidence": 0.6,
                "_benefit_clause_idx": i,
                "_clause_id": cid,
            })

    return {
        "benefit_rules": benefit_rules,
        "exclusions": exclusions,
        "evidence_requirements": evidence_requirements,
        "conditions": conditions,
        "assignment_applicability": assignment_applicability,
        "family_applicability": family_applicability,
        "source_links": source_links,
    }


def run_normalization(
    db: Any,
    policy_document: Dict[str, Any],
    clauses: List[Dict[str, Any]],
    created_by: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run full normalization: create/attach company_policy, create policy_version,
    persist benefit_rules, exclusions, evidence_requirements, conditions, applicability,
    and policy_source_links. Returns {policy_id, policy_version_id, summary}.
    The created policy_version is versioned (version_number) and traceable to the
    source document (source_policy_document_id) and to source clauses (policy_source_links).
    """
    company_id = (policy_document.get("company_id") or "").strip() or None
    if not company_id:
        raise ValueError("Policy document has no company_id. Re-upload the document from the company's policy workspace.")
    doc_id = policy_document.get("id")
    meta = policy_document.get("extracted_metadata") or {}
    title = meta.get("detected_title") or meta.get("policy_title") or policy_document.get("filename", "Policy")
    version_label = meta.get("detected_version") or meta.get("version") or policy_document.get("version_label")
    effective_date = meta.get("detected_effective_date") or meta.get("effective_date")

    # Build file_url from storage_path for company_policy (object key only, no bucket prefix)
    storage_path = policy_document.get("storage_path") or ""
    file_url = storage_path or ""

    # Get or create company_policy
    policies = db.list_company_policies(company_id)
    if policies:
        policy_id = policies[0]["id"]
    else:
        policy_id = str(uuid.uuid4())
        db.create_company_policy(
            policy_id=policy_id,
            company_id=company_id,
            title=title[:200],
            version=version_label,
            effective_date=effective_date,
            file_url=file_url or "policy-document",  # object key only, e.g. companies/.../policy-documents/.../file.pdf
            file_type=policy_document.get("mime_type", "").split("/")[-1] or "pdf",
            created_by=created_by,
            request_id=request_id,
        )

    # Next version number
    existing = db.list_policy_versions(policy_id)
    version_number = max((v.get("version_number") or 1 for v in existing), default=1) + 1 if existing else 1

    # Normalize clauses to objects
    result = normalize_clauses_to_objects(clauses, doc_id)

    # Create policy_version
    version_id = str(uuid.uuid4())
    db.create_policy_version(
        version_id=version_id,
        policy_id=policy_id,
        source_policy_document_id=doc_id,
        version_number=version_number,
        status="auto_generated",
        auto_generated=True,
        review_status="pending",
        confidence=0.7,
        created_by=created_by,
        request_id=request_id,
    )

    benefit_idx_to_id: Dict[int, str] = {}

    # Insert benefit rules
    for r in result["benefit_rules"]:
        r["policy_version_id"] = version_id
        rid = db.insert_policy_benefit_rule(r)
        idx = r.get("_clause_idx")
        if idx is not None:
            benefit_idx_to_id[idx] = rid

    # Insert exclusions
    exclusion_ids: List[Tuple[str, str]] = []
    for e in result["exclusions"]:
        e["policy_version_id"] = version_id
        eid = db.insert_policy_exclusion(e)
        exclusion_ids.append((eid, e.get("_clause_id")))

    # Insert evidence requirements
    evidence_ids: List[Tuple[str, str]] = []
    for ev in result["evidence_requirements"]:
        ev["policy_version_id"] = version_id
        evid = db.insert_policy_evidence_requirement(ev)
        evidence_ids.append((evid, ev.get("_clause_id")))

    # Insert conditions - need object_id from benefit_rule
    first_benefit_id = next(iter(benefit_idx_to_id.values()), None)
    for c in result["conditions"]:
        c["policy_version_id"] = version_id
        idx = c.get("_benefit_clause_idx")
        if idx is not None and idx in benefit_idx_to_id:
            c["object_id"] = benefit_idx_to_id[idx]
        elif first_benefit_id:
            c["object_id"] = first_benefit_id
        else:
            continue
        db.insert_policy_rule_condition(c)

    # Insert assignment applicability
    for a in result["assignment_applicability"]:
        idx = a.get("_benefit_clause_idx")
        if idx is not None and idx in benefit_idx_to_id:
            a["policy_version_id"] = version_id
            a["benefit_rule_id"] = benefit_idx_to_id[idx]
            db.insert_policy_assignment_applicability(a)

    # Insert family applicability
    for f in result["family_applicability"]:
        idx = f.get("_benefit_clause_idx")
        if idx is not None and idx in benefit_idx_to_id:
            f["policy_version_id"] = version_id
            f["benefit_rule_id"] = benefit_idx_to_id[idx]
            db.insert_policy_family_applicability(f)

    def _source_link_for_clause(clause_id: Optional[str], obj_type: str, obj_id: str) -> None:
        if not clause_id:
            return
        for cl in clauses:
            if cl.get("id") == clause_id:
                link = {
                    "policy_version_id": version_id,
                    "object_type": obj_type,
                    "object_id": obj_id,
                    "clause_id": clause_id,
                    "source_page_start": cl.get("source_page_start"),
                    "source_page_end": cl.get("source_page_end"),
                    "source_anchor": cl.get("source_anchor"),
                }
                db.insert_policy_source_link(link)
                return

    for r in result["benefit_rules"]:
        idx = r.get("_clause_idx")
        cid = r.get("_clause_id")
        if idx is not None and idx in benefit_idx_to_id and cid:
            _source_link_for_clause(cid, "benefit_rule", benefit_idx_to_id[idx])

    for eid, cid in exclusion_ids:
        _source_link_for_clause(cid, "exclusion", eid)

    for evid, cid in evidence_ids:
        _source_link_for_clause(cid, "evidence_requirement", evid)

    by_category: Dict[str, int] = {}
    for r in result["benefit_rules"]:
        cat = r.get("benefit_category") or "misc"
        by_category[cat] = by_category.get(cat, 0) + 1
    for t in POLICY_THEMES:
        if t not in by_category:
            by_category[t] = 0

    return {
        "policy_id": policy_id,
        "policy_version_id": version_id,
        "summary": {
            "benefit_rules": len(result["benefit_rules"]),
            "exclusions": len(result["exclusions"]),
            "evidence_requirements": len(result["evidence_requirements"]),
            "conditions": len(result["conditions"]),
            "by_category": by_category,
        },
    }
