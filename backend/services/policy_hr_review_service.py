"""
HR-facing aggregate payload for reviewing normalized drafts vs Layer-2 publishable rows.

Used by GET /api/hr/policy-review (document_id and/or policy_id).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .policy_document_intake import SCOPE_LONG_TERM
from .policy_normalization import normalize_clauses_to_objects
from .policy_normalization_draft import build_normalization_draft_model, parse_stored_normalization_draft
from .policy_normalization_errors import PolicyNormalizationFieldIssue
from .policy_normalization_validate import NormalizationReadinessResult, evaluate_normalization_readiness
from .policy_pipeline_layers import enrich_policy_document_for_hr
from .policy_hr_rule_override_layer import (
    build_effective_entitlement_preview,
    merge_benefit_rules_for_effective_readiness,
)
from .policy_processing_readiness import evaluate_stored_policy_readiness


def _strip_layer2_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in row.items() if not str(k).startswith("_")}


def _load_layer2_lists(db: Any, version_id: str) -> Dict[str, List[Dict[str, Any]]]:
    return {
        "benefit_rules": list(db.list_policy_benefit_rules(version_id) or []),
        "exclusions": list(db.list_policy_exclusions(version_id) or []),
        "conditions": list(db.list_policy_rule_conditions(version_id) or []),
        "evidence_requirements": list(db.list_policy_evidence_requirements(version_id) or []),
        "assignment_applicability": list(db.list_policy_assignment_applicability(version_id) or []),
        "family_applicability": list(db.list_policy_family_applicability(version_id) or []),
    }


def _layer2_publishable_payload(layer: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    br = [_strip_layer2_row(dict(r)) for r in layer["benefit_rules"]]
    ex = [_strip_layer2_row(dict(r)) for r in layer["exclusions"]]
    cond = [_strip_layer2_row(dict(r)) for r in layer["conditions"]]
    ev = [_strip_layer2_row(dict(r)) for r in layer["evidence_requirements"]]
    aa = [_strip_layer2_row(dict(r)) for r in layer["assignment_applicability"]]
    fa = [_strip_layer2_row(dict(r)) for r in layer["family_applicability"]]
    return {
        "benefit_rules": br,
        "exclusions": ex,
        "conditions": cond,
        "evidence_requirements": ev,
        "assignment_applicability": aa,
        "family_applicability": fa,
        "counts": {
            "benefit_rules": len(br),
            "exclusions": len(ex),
            "conditions": len(cond),
            "evidence_requirements": len(ev),
            "assignment_applicability": len(aa),
            "family_applicability": len(fa),
        },
    }


def _template_policy_document_stub(policy: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": None,
        "company_id": policy.get("company_id"),
        "processing_status": "complete",
        "detected_document_type": "starter_template",
        "detected_policy_scope": SCOPE_LONG_TERM,
        "extracted_metadata": {"source": "starter_template"},
        "filename": (policy.get("title") or "policy_template")[:200],
        "version_label": None,
        "effective_date": None,
    }


def _build_mapped_for_draft(
    db: Any,
    *,
    clauses: List[Dict[str, Any]],
    doc_id: Optional[str],
    version: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    live = normalize_clauses_to_objects(clauses, str(doc_id) if doc_id else "")
    if not version or not version.get("id"):
        return live
    vid = str(version["id"])
    layer = _load_layer2_lists(db, vid)
    return {
        "benefit_rules": layer["benefit_rules"],
        "exclusions": layer["exclusions"],
        "conditions": layer["conditions"],
        "evidence_requirements": layer["evidence_requirements"],
        "assignment_applicability": layer["assignment_applicability"],
        "family_applicability": layer["family_applicability"],
        "draft_rule_candidates": live.get("draft_rule_candidates") or [],
        "source_links": live.get("source_links") or [],
    }


def _policy_document_for_draft(
    doc: Optional[Dict[str, Any]],
    policy: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if doc:
        return doc
    if policy:
        return _template_policy_document_stub(policy)
    return {
        "id": None,
        "company_id": None,
        "processing_status": "unknown",
        "detected_document_type": None,
        "detected_policy_scope": "unknown",
        "extracted_metadata": {},
        "filename": None,
    }


def _resolve_ids_for_draft(
    doc: Optional[Dict[str, Any]],
    policy: Optional[Dict[str, Any]],
    version: Optional[Dict[str, Any]],
) -> Tuple[str, str, str]:
    company_id = ""
    if doc and doc.get("company_id"):
        company_id = str(doc["company_id"])
    elif policy and policy.get("company_id"):
        company_id = str(policy["company_id"])
    pid = str(policy["id"]) if policy and policy.get("id") else ""
    if not pid:
        if doc and doc.get("id"):
            pid = f"unlinked-document-{doc['id']}"
        else:
            pid = "unlinked-policy"
    pvid = str(version["id"]) if version and version.get("id") else ""
    if not pvid:
        anchor = (doc or {}).get("id") or pid
        pvid = f"preview-version-{anchor}"
    return company_id, pid, pvid


def _aggregate_issues(
    readiness_env: Dict[str, Any],
    norm_core: Optional[NormalizationReadinessResult] = None,
    draft_readiness: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    for tier in ("normalization_readiness", "publish_readiness", "comparison_readiness"):
        sl = readiness_env.get(tier) or {}
        for it in sl.get("issues") or []:
            issues.append(
                {
                    "tier": tier,
                    "code": it.get("code"),
                    "message": it.get("message"),
                    "field": it.get("field"),
                }
            )
    crc = readiness_env.get("comparison_rule_readiness") or {}
    if crc.get("comparison_ready_strict") is False:
        pl = crc.get("policy_level")
        if isinstance(pl, str) and pl.strip():
            msg = f"Policy-level rule comparison is {pl!r} (strict full comparison not met)."
        else:
            msg = "Rule-level comparison is not strict-ready for all required benefits."
        issues.append(
            {
                "tier": "comparison_rule_readiness",
                "code": "COMPARISON_RULES_NOT_STRICT_READY",
                "message": msg,
                "field": None,
            }
        )
    if norm_core and norm_core.draft_blocked:
        for b in norm_core.draft_block_details or []:
            if isinstance(b, PolicyNormalizationFieldIssue):
                issues.append(
                    {
                        "tier": "normalization_gate",
                        "code": "DRAFT_BLOCKED",
                        "message": b.issue,
                        "field": b.field,
                    }
                )
    if draft_readiness:
        for tier in ("normalization_readiness", "publish_readiness", "comparison_readiness"):
            sl = draft_readiness.get(tier) or {}
            for it in sl.get("issues") or []:
                code = it.get("code")
                if any(x.get("tier") == f"draft_{tier}" and x.get("code") == code for x in issues):
                    continue
                issues.append(
                    {
                        "tier": f"draft_{tier}",
                        "code": code,
                        "message": it.get("message"),
                        "field": it.get("field"),
                    }
                )
    return issues


def _missing_structure_notes(norm_core: Optional[NormalizationReadinessResult]) -> List[Dict[str, Any]]:
    if not norm_core:
        return []
    out: List[Dict[str, Any]] = []
    for issue in norm_core.readiness_issues or []:
        if isinstance(issue, PolicyNormalizationFieldIssue):
            out.append({"field": issue.field, "issue": issue.issue})
    return out


def _employee_visibility(readiness_env: Dict[str, Any], published: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    pub_ok = bool(published and str(published.get("status") or "").lower() == "published")
    pr = readiness_env.get("publish_readiness") or {}
    cr = readiness_env.get("comparison_readiness") or {}
    crc = readiness_env.get("comparison_rule_readiness") or {}
    return {
        "employee_sees_published_policy_matrix": pub_ok,
        "publish_readiness_status": pr.get("status"),
        "comparison_readiness_status": cr.get("status"),
        "comparison_ready_strict": crc.get("comparison_ready_strict"),
    }


def build_hr_policy_review_payload(
    db: Any,
    *,
    document_id: Optional[str] = None,
    policy_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Assemble HR review payload. Caller must enforce auth (document / policy access).

    Either document_id or policy_id (or both) must be provided. When both are set and a version
    exists for the document, policy_id must match that version's policy_id.
    """
    did = str(document_id).strip() if document_id else None
    pid_in = str(policy_id).strip() if policy_id else None
    if not did and not pid_in:
        raise ValueError("Provide document_id and/or policy_id")

    doc: Optional[Dict[str, Any]] = None
    clauses: List[Dict[str, Any]] = []
    policy: Optional[Dict[str, Any]] = None
    version: Optional[Dict[str, Any]] = None

    if did:
        doc = db.get_policy_document(did, request_id=request_id)
        if not doc:
            raise ValueError("Document not found")
        clauses = list(db.list_policy_document_clauses(did, request_id=request_id) or [])
        vers = db.list_policy_versions_by_source_document(did)
        version = vers[0] if vers else None
        if version and version.get("policy_id"):
            policy = db.get_company_policy(str(version["policy_id"]))

    if pid_in:
        pol = db.get_company_policy(pid_in)
        if not pol:
            raise ValueError("Policy not found")
        if policy and str(policy.get("id")) != str(pol.get("id")):
            raise ValueError("policy_id does not match the policy linked to this document")
        if not did:
            policy = pol
            version = db.get_latest_policy_version(pid_in)
            src = (version or {}).get("source_policy_document_id")
            if src:
                doc = db.get_policy_document(str(src), request_id=request_id)
                if doc:
                    clauses = list(db.list_policy_document_clauses(str(src), request_id=request_id) or [])
        elif not policy:
            policy = pol
            if version and str(version.get("policy_id")) != str(pol.get("id")):
                raise ValueError("policy_id does not match the policy linked to this document")

    if did and pid_in and version and str(version.get("policy_id")) != pid_in:
        raise ValueError("policy_id does not match the policy linked to this document")

    published: Optional[Dict[str, Any]] = None
    if policy and policy.get("id"):
        published = db.get_published_policy_version(str(policy["id"]))

    layer_lists: Dict[str, List[Dict[str, Any]]] = {
        "benefit_rules": [],
        "exclusions": [],
        "conditions": [],
        "evidence_requirements": [],
        "assignment_applicability": [],
        "family_applicability": [],
    }
    if version and version.get("id"):
        layer_lists = _load_layer2_lists(db, str(version["id"]))

    br_for_readiness = layer_lists["benefit_rules"]
    if version and version.get("id"):
        try:
            br_for_readiness = merge_benefit_rules_for_effective_readiness(
                db, str(version["id"]), layer_lists["benefit_rules"]
            )
        except Exception:
            br_for_readiness = layer_lists["benefit_rules"]
    policy_readiness = evaluate_stored_policy_readiness(
        latest_version=version,
        published_version=published,
        benefit_rules=br_for_readiness,
        exclusions=layer_lists["exclusions"],
        conditions=layer_lists["conditions"],
        assignment_applicability=layer_lists["assignment_applicability"],
        source_document=doc,
    )

    stored_draft = None
    if version:
        stored_draft = parse_stored_normalization_draft(version.get("normalization_draft_json"))

    doc_id_for_norm = str(doc["id"]) if doc and doc.get("id") else None
    mapped = _build_mapped_for_draft(db, clauses=clauses, doc_id=doc_id_for_norm, version=version)
    policy_document = _policy_document_for_draft(doc, policy)
    norm_core = evaluate_normalization_readiness(
        policy_document,
        mapped,
        request_id=request_id,
        document_id=doc_id_for_norm,
    )

    if stored_draft:
        normalization_draft = stored_draft
        draft_readiness = normalization_draft.get("readiness")
    else:
        company_id, pid_draft, pvid_draft = _resolve_ids_for_draft(doc, policy, version)
        normalization_draft = build_normalization_draft_model(
            policy_document=policy_document,
            company_id=company_id,
            policy_id=pid_draft,
            policy_version_id=pvid_draft,
            clauses=clauses,
            mapped=mapped,
            norm_core=norm_core,
        )
        draft_readiness = normalization_draft.get("readiness")

    source_enriched = enrich_policy_document_for_hr(doc) if doc else None
    detected = {
        "detected_document_type": (doc or policy_document).get("detected_document_type"),
        "detected_policy_scope": (doc or policy_document).get("detected_policy_scope"),
        "processing_status": (doc or policy_document).get("processing_status"),
        "layer1": (source_enriched or {}).get("layer1") if source_enriched else None,
    }

    issues = _aggregate_issues(policy_readiness, norm_core=norm_core, draft_readiness=draft_readiness)
    missing_structure = _missing_structure_notes(norm_core)

    layer2_pub = _layer2_publishable_payload(layer_lists)

    hr_overrides: List[Dict[str, Any]] = []
    entitlement_effective_preview: List[Dict[str, Any]] = []
    if version and version.get("id"):
        try:
            hr_overrides = list(db.list_hr_benefit_rule_overrides(str(version["id"])) or [])
        except Exception:
            hr_overrides = []
        try:
            entitlement_effective_preview = build_effective_entitlement_preview(
                db, str(version["id"]), layer_lists["benefit_rules"]
            )
        except Exception:
            entitlement_effective_preview = []

    return {
        "review": {
            "document_id": did,
            "policy_id": str(policy["id"]) if policy and policy.get("id") else None,
            "policy_version_id": str(version["id"]) if version and version.get("id") else None,
            "has_persisted_version": bool(version and version.get("id")),
            "normalization_draft_source": "stored" if stored_draft else "synthesized",
        },
        "source_document": source_enriched,
        "detected_classification": detected,
        "normalization_draft": normalization_draft,
        "clause_candidates": normalization_draft.get("clause_candidates") or [],
        "rule_candidates": normalization_draft.get("rule_candidates") or {},
        "draft_rule_candidates": normalization_draft.get("draft_rule_candidates") or [],
        "layer2_publishable": layer2_pub,
        "readiness": policy_readiness,
        "issues": issues,
        "missing_structure": missing_structure,
        "employee_visibility": _employee_visibility(policy_readiness, published),
        "mapper_preview": {
            "from_clause_mapping": {
                "benefit_rules_count": len(mapped.get("benefit_rules") or []),
                "exclusions_count": len(mapped.get("exclusions") or []),
                "draft_rule_candidates_count": len(mapped.get("draft_rule_candidates") or []),
            },
            "from_database_layer2": layer2_pub["counts"],
        },
        "hr_overrides": hr_overrides,
        "entitlement_effective_preview": entitlement_effective_preview,
    }
