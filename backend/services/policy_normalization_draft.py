"""
Normalized draft model persisted on policy_versions.normalization_draft_json.

Captures useful structure from intake even when Layer-2 benefit/exclusion rows are empty or not
yet publishable. Employee publish and comparison gates still use relational Layer-2 + readiness.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from .policy_pipeline_layers import layer1_fields_for_company_policy_shell
from .policy_taxonomy import resolve_benefit_key, resolve_theme, get_benefit_meta
from .policy_grouped_comparison_readiness import build_comparison_engine_grouped_readiness_payload
from .policy_grouped_policy_model import build_grouped_policy_review_view
from .policy_hr_grouped_review import build_grouped_hr_review
from .policy_template_first_import import build_template_first_import_payload
from .policy_processing_readiness import build_processing_readiness_envelope
from .policy_normalization_validate import NormalizationReadinessResult

SCHEMA_VERSION = 1


def _strip_internal(obj: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in obj.items() if not str(k).startswith("_")}


def _infer_default_currency(
    mapped: Dict[str, Any],
    clauses: Sequence[Dict[str, Any]],
    extracted_metadata: Optional[Dict[str, Any]],
) -> Optional[str]:
    for r in mapped.get("benefit_rules") or []:
        c = (r.get("currency") or "").strip()
        if c:
            return c
    for c in clauses:
        hints = c.get("normalized_hint_json") if isinstance(c.get("normalized_hint_json"), dict) else {}
        cur = (hints.get("candidate_currency") or "").strip()
        if cur:
            return cur
    if isinstance(extracted_metadata, dict):
        u = extracted_metadata.get("mentioned_units")
        if isinstance(u, list):
            for x in u:
                if isinstance(x, str) and len(x) == 3 and x.isalpha():
                    return x.upper()
    return None


def _assignment_hints(policy_document: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    em = policy_document.get("extracted_metadata")
    if isinstance(em, dict):
        raw = em.get("mentioned_assignment_types") or em.get("assignment_types_mentioned")
        if isinstance(raw, list):
            out.extend(str(x) for x in raw if x)
        elif isinstance(raw, str) and raw.strip():
            out.append(raw.strip())
    return sorted(set(out))


def build_clause_candidates(clauses: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for c in clauses:
        if not isinstance(c, dict):
            continue
        raw = (c.get("raw_text") or "") or ""
        hints = c.get("normalized_hint_json") if isinstance(c.get("normalized_hint_json"), dict) else {}
        section = c.get("section_label")
        ctype = c.get("clause_type") or "unknown"
        benefit_guess = resolve_benefit_key(
            hints.get("candidate_benefit_key"),
            section,
            raw,
        )
        theme = None
        if benefit_guess:
            meta = get_benefit_meta(benefit_guess)
            theme = resolve_theme(benefit_guess, meta.get("group"))
        nums = hints.get("candidate_numeric_values")
        if not isinstance(nums, list):
            nums = []
        ats = hints.get("candidate_assignment_types")
        if not isinstance(ats, list):
            ats = []
        fts = hints.get("candidate_family_status_terms")
        if not isinstance(fts, list):
            fts = []
        rows.append(
            {
                "clause_id": c.get("id"),
                "clause_type": ctype,
                "section_label": section,
                "raw_text_preview": raw[:500],
                "intent_category": theme or (str(ctype) if ctype != "unknown" else None),
                "service_match_candidate_benefit_key": benefit_guess,
                "confidence": c.get("confidence"),
                "limit_fragments": {
                    "numeric_values": nums[:12],
                    "currency": hints.get("candidate_currency"),
                    "unit": hints.get("candidate_unit"),
                    "frequency": hints.get("candidate_frequency"),
                },
                "applicability_fragments": {
                    "assignment_types": [str(x) for x in ats[:24]],
                    "family_status_terms": [str(x) for x in fts[:24]],
                },
            }
        )
    return rows


def build_rule_candidates(mapped: Dict[str, Any]) -> Dict[str, Any]:
    def annotate_benefit(r: Dict[str, Any]) -> Dict[str, Any]:
        o = _strip_internal(r)
        o["publishable_under_current_gate"] = True
        o["kind"] = "benefit_rule"
        return o

    def annotate_excl(r: Dict[str, Any]) -> Dict[str, Any]:
        o = _strip_internal(r)
        o["publishable_under_current_gate"] = True
        o["kind"] = "exclusion"
        return o

    def annotate_ev(r: Dict[str, Any]) -> Dict[str, Any]:
        o = _strip_internal(r)
        o["publishable_under_current_gate"] = False
        o["kind"] = "evidence_requirement"
        return o

    def annotate_cond(r: Dict[str, Any]) -> Dict[str, Any]:
        o = _strip_internal(r)
        o["publishable_under_current_gate"] = False
        o["kind"] = "condition"
        return o

    return {
        "benefit_rules": [annotate_benefit(dict(r)) for r in (mapped.get("benefit_rules") or [])],
        "exclusions": [annotate_excl(dict(r)) for r in (mapped.get("exclusions") or [])],
        "evidence_requirements": [annotate_ev(dict(r)) for r in (mapped.get("evidence_requirements") or [])],
        "conditions": [annotate_cond(dict(r)) for r in (mapped.get("conditions") or [])],
    }


def build_normalization_draft_model(
    *,
    policy_document: Dict[str, Any],
    company_id: str,
    policy_id: str,
    policy_version_id: str,
    clauses: Sequence[Dict[str, Any]],
    mapped: Dict[str, Any],
    norm_core: NormalizationReadinessResult,
) -> Dict[str, Any]:
    shell = layer1_fields_for_company_policy_shell(
        policy_document.get("extracted_metadata"),
        filename=policy_document.get("filename"),
        version_label_row=policy_document.get("version_label"),
        effective_date_row=policy_document.get("effective_date"),
    )
    em = policy_document.get("extracted_metadata") if isinstance(policy_document.get("extracted_metadata"), dict) else {}
    readiness = build_processing_readiness_envelope(policy_document, clauses, mapped, norm_core)
    draft_list = list(mapped.get("draft_rule_candidates") or [])
    grouped_items, comparison_subrules = build_grouped_policy_review_view(clauses, draft_list)
    grouped_policy_comparison_engine_input = build_comparison_engine_grouped_readiness_payload(grouped_items)
    template_first_import = build_template_first_import_payload(
        clauses,
        draft_list,
        grouped_policy_items_count=len(grouped_items),
    )
    grouped_review = build_grouped_hr_review(
        grouped_items,
        clauses,
        draft_list,
        template_first_import=template_first_import,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "document_metadata": {
            "policy_name": (shell.get("title") or "Policy")[:300],
            "detected_document_type": (policy_document.get("detected_document_type") or "").strip() or None,
            "detected_policy_scope": (policy_document.get("detected_policy_scope") or "").strip() or None,
            "assignment_type_hints": _assignment_hints(policy_document),
            "default_currency": _infer_default_currency(mapped, clauses, em),
            "source_policy_document_id": str(policy_document.get("id")) if policy_document.get("id") else None,
            "company_id": str(company_id).strip() or None,
            "policy_id": str(policy_id),
            "policy_version_id": str(policy_version_id),
            "processing_status": (policy_document.get("processing_status") or "").strip() or None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "clause_candidates": build_clause_candidates(clauses),
        "rule_candidates": build_rule_candidates(mapped),
        "draft_rule_candidates": list(mapped.get("draft_rule_candidates") or []),
        "grouped_policy_items": grouped_items,
        "comparison_subrules": comparison_subrules,
        "grouped_policy_comparison_engine_input": grouped_policy_comparison_engine_input,
        "template_first_import": template_first_import,
        "grouped_review": grouped_review,
        "readiness": readiness,
    }


def parse_stored_normalization_draft(raw: Any) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return None
