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
import math
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from sqlalchemy.exc import IntegrityError, OperationalError

from .policy_normalization_errors import PolicyNormalizationFieldIssue, PolicyNormalizationPayloadInvalid
from .policy_normalization_validate import (
    build_version_payload_for_validation,
    evaluate_normalization_readiness,
    json_preview_for_diagnostics,
    log_extraction_and_normalization_shape,
    validate_benefit_rules_payload,
    validate_conditions_payload,
    validate_exclusions_payload,
    validate_policy_version_payload,
)
from .policy_taxonomy import (
    ASSIGNMENT_TYPE_MAP,
    FAMILY_STATUS_MAP,
    POLICY_THEMES,
    resolve_benefit_key,
    get_benefit_meta,
    resolve_theme,
)
from .policy_pipeline_layers import layer1_fields_for_company_policy_shell

log = logging.getLogger(__name__)

# Must match policy_benefit_rules.calc_type CHECK in migrations
ALLOWED_CALC_TYPES = frozenset(
    {
        "percent_salary",
        "flat_amount",
        "unit_cap",
        "reimbursement",
        "difference_only",
        "per_diem",
        "other",
    }
)

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
    m = re.search(
        r"(?:EUR|USD|GBP|CHF|CAD|AUD|SGD|NZD)\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)",
        raw_text,
        re.I,
    )
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
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


# Clause types eligible for publish-layer benefit_rules when signals are strong enough.
_BENEFITISH_CLAUSE_TYPES = frozenset(
    {
        "benefit",
        "tax_rule",
        "unknown",
        "scope",
        "eligibility",
        "definition",
        "lifecycle_rule",
        "approval_rule",
    }
)

_VAGUE_COVERAGE_RE = re.compile(
    r"\b(?:may|might|could|can be|subject to|depending on|at (?:the )?discretion|where appropriate|as appropriate|"
    r"on a case[- ]by[- ]case basis|if approved|when approved|as needed)\b",
    re.I,
)

_EXCLUSION_PHRASES = (
    "not covered",
    "no coverage",
    "does not cover",
    "not eligible",
    "excludes",
    "excluded",
    "not available",
    "will not be provided",
    "will not cover",
    "not payable",
    "not reimbursed",
    "without coverage",
)


def _text_suggests_exclusion_language(raw: str) -> bool:
    rl = (raw or "").lower()
    return any(p in rl for p in _EXCLUSION_PHRASES)


def _extract_currency_hint(raw: str, hints: Dict[str, Any]) -> Optional[str]:
    c = hints.get("candidate_currency")
    if c and str(c).strip():
        return str(c).strip().upper()
    ru = (raw or "").upper()
    for token in ("EUR", "USD", "GBP", "CHF", "CAD", "AUD", "SGD", "NZD"):
        if token in ru:
            return token
    if "€" in (raw or ""):
        return "EUR"
    if "£" in (raw or ""):
        return "GBP"
    if "$" in (raw or ""):
        return "USD"
    return None


def _has_structured_monetary_cap(raw: str, hints: Dict[str, Any]) -> bool:
    nums = hints.get("candidate_numeric_values") or []
    if nums:
        try:
            if float(nums[0]) > 0:
                if hints.get("candidate_currency") or _extract_currency_hint(raw, hints):
                    return True
                if "%" in raw or re.search(r"\bpercent\b", raw, re.I):
                    return True
        except (TypeError, ValueError):
            pass
    av = _extract_amount_value(hints, raw)
    if av is not None and av > 0:
        if _extract_currency_hint(raw, hints):
            return True
        if "%" in raw or "percent" in raw.lower() or "salary" in raw.lower():
            return True
    return False


def _is_vague_coverage_framing(raw: str, has_structured_cap: bool) -> bool:
    if has_structured_cap:
        return False
    return bool(_VAGUE_COVERAGE_RE.search(raw or ""))


def _role_hints_from_text(raw: str) -> List[str]:
    rl = (raw or "").lower()
    out: List[str] = []
    if re.search(r"\bdirectors?\b", rl):
        out.append("directors")
    if re.search(r"\bexecutives?\b|\bsenior management\b|\bc[- ]suite\b", rl):
        out.append("executives")
    return out


def _family_terms_from_text(raw: str) -> List[str]:
    rl = (raw or "").lower()
    out: List[str] = []
    if re.search(r"\bsingle(?:\s+employees?)?\b|\bunmarried\b", rl):
        out.append("single")
    if "married" in rl or "spouse" in rl or "accompanied" in rl:
        out.append("family_context")
    return out


def _duration_quantity_fragment(raw: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    m = re.search(r"(\d{1,4})\s*(?:additional\s+)?(nights?|days?)\b", raw or "", re.I)
    if m:
        out["quantity"] = int(m.group(1))
        out["unit"] = "nights" if "night" in m.group(2).lower() else "days"
    return out


def _assignment_types_from_text(raw: str) -> List[str]:
    """Infer assignment types from free text when hints are missing (weakly structured summaries)."""
    rl = (raw or "").lower()
    out: List[str] = []
    if re.search(r"long[-\s]term", rl):
        m = ASSIGNMENT_TYPE_MAP.get("long_term")
        if m and m not in out:
            out.append(m)
    if re.search(r"short[-\s]term", rl):
        m = ASSIGNMENT_TYPE_MAP.get("short_term")
        if m and m not in out:
            out.append(m)
    if re.search(r"\bcommuter\b", rl):
        m = ASSIGNMENT_TYPE_MAP.get("commuter")
        if m and m not in out:
            out.append(m)
    if re.search(r"\bpermanent\b", rl) and "assignment" in rl:
        m = ASSIGNMENT_TYPE_MAP.get("permanent")
        if m and m not in out:
            out.append(m)
    return out


def _should_publish_exclusion_row(
    ctype: str, hints: Dict[str, Any], raw: str, benefit_key: Optional[str], has_structured_cap: bool
) -> bool:
    if ctype == "exclusion":
        return True
    if hints.get("candidate_exclusion_flag"):
        return True
    if not _text_suggests_exclusion_language(raw):
        return False
    rl = (raw or "").lower()
    if benefit_key:
        return True
    if any(k in rl for k in ("tax equalization", "hypothetical tax", "tax protection")):
        return True
    # Avoid turning a mixed benefit+exclusion sentence into exclusion-only (suppresses benefit row).
    if has_structured_cap:
        return False
    return True


def _should_publish_benefit_row(
    ctype: str,
    benefit_key: Optional[str],
    exclusion_published: bool,
    vague: bool,
    has_cap: bool,
) -> bool:
    if exclusion_published:
        return False
    if ctype == "exclusion":
        return False
    if not benefit_key:
        return False
    if ctype not in _BENEFITISH_CLAUSE_TYPES:
        return False
    if vague and not has_cap:
        return False
    return True


def _coverage_status(
    exclusion_intent: bool, has_cap: bool, vague: bool, benefit_key: Optional[str]
) -> str:
    if exclusion_intent:
        return "excluded"
    if has_cap:
        return "capped"
    if benefit_key and vague:
        return "conditional"
    if benefit_key:
        return "mentioned"
    return "unknown"


def normalize_clauses_to_objects(
    clauses: List[Dict[str, Any]], doc_id: str
) -> Dict[str, Any]:
    """
    Convert policy_document_clauses into canonical objects.

    Two levels:
    - **draft_rule_candidates**: every clause with policy-relevant signal (coverage, exclusion,
      caps, applicability) — including narrative / vague wording that must not be silently dropped.
    - **Publish-layer** lists (benefit_rules, exclusions, …): only when structure satisfies
      current mapping rules (explicit caps, clear exclusions, non-vague benefit language, etc.).
    """
    benefit_rules: List[Dict[str, Any]] = []
    exclusions: List[Dict[str, Any]] = []
    evidence_requirements: List[Dict[str, Any]] = []
    conditions: List[Dict[str, Any]] = []
    assignment_applicability: List[Dict[str, Any]] = []
    family_applicability: List[Dict[str, Any]] = []
    source_links: List[Dict[str, Any]] = []
    draft_rule_candidates: List[Dict[str, Any]] = []

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

        benefit_key = resolve_benefit_key(
            hints.get("candidate_benefit_key"),
            section,
            raw,
        )
        theme_guess: Optional[str] = None
        if benefit_key:
            meta = get_benefit_meta(benefit_key)
            theme_guess = resolve_theme(benefit_key, meta.get("group"))

        exclusion_intent = (
            ctype == "exclusion"
            or bool(hints.get("candidate_exclusion_flag"))
            or _text_suggests_exclusion_language(raw)
        )
        has_cap = _has_structured_monetary_cap(raw, hints)
        vague = _is_vague_coverage_framing(raw, has_cap)
        cov_status = _coverage_status(exclusion_intent, has_cap, vague, benefit_key)

        amount_value = _extract_amount_value(hints, raw)
        currency = hints.get("candidate_currency") or _extract_currency_hint(raw, hints)
        amount_unit = hints.get("candidate_unit")
        dur_frag = _duration_quantity_fragment(raw)
        ats = _normalize_assignment_types(hints)
        for at in _assignment_types_from_text(raw):
            if at not in ats:
                ats.append(at)
        fts_hint = _normalize_family_status(hints)
        fts_text = _family_terms_from_text(raw)
        role_hints = _role_hints_from_text(raw)

        publish_targets: List[str] = []
        pub_assessment = "draft_only"

        exclusion_published = False
        if _should_publish_exclusion_row(ctype, hints, raw, benefit_key, has_cap):
            domain = "scope"
            rl = raw.lower()
            if any(s in rl for s in ["tax", "tax equalization", "hypothetical"]):
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
            exclusion_published = True
            publish_targets.append("exclusions")
            pub_assessment = "publish_exclusion"

        benefit_emitted = False
        if _should_publish_benefit_row(ctype, benefit_key, exclusion_published, vague, has_cap):
            meta = get_benefit_meta(benefit_key or "")
            theme = resolve_theme(benefit_key or "", meta.get("group"))
            calc_type = _detect_calc_type(raw, hints, benefit_key or "")
            frequency = hints.get("candidate_frequency") or "per_assignment"
            rule = {
                "benefit_key": benefit_key,
                "benefit_category": theme,
                "calc_type": calc_type,
                "amount_value": amount_value,
                "amount_unit": amount_unit,
                "currency": currency if isinstance(currency, str) else None,
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
            benefit_emitted = True
            publish_targets.append("benefit_rules")
            pub_assessment = "publish_benefit_rule"

            for at in ats:
                assignment_applicability.append({
                    "_benefit_clause_idx": i,
                    "assignment_type": at,
                })
            for fs in fts_hint:
                family_applicability.append({
                    "_benefit_clause_idx": i,
                    "family_status": fs,
                })

        # Publish-layer conditions only when the same clause produced a benefit rule (avoid orphan scope).
        if benefit_emitted:
            for at in ats:
                conditions.append({
                    "object_type": "benefit_rule",
                    "object_id": None,
                    "condition_type": "assignment_type",
                    "condition_value_json": {"assignment_types": [at]},
                    "auto_generated": True,
                    "review_status": "pending",
                    "confidence": conf,
                    "_benefit_clause_idx": i,
                    "_clause_id": cid,
                })
            for fs in fts_hint:
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
            m = re.search(r"(\d{1,3})\s*(?:months?|years?)", raw, re.I)
            if m and any(w in raw.lower() for w in ("assignment", "duration", "longer than", "exceeds")):
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
                publish_targets.append("conditions")
                if pub_assessment == "publish_benefit_rule":
                    pub_assessment = "publish_benefit_rule_with_conditions"

        # Evidence (unchanged heuristics)
        if ctype == "evidence_rule" or hints.get("candidate_evidence_items"):
            items = hints.get("candidate_evidence_items") or []
            if not items and "receipt" in raw.lower():
                items = ["receipts"]
            if items:
                evidence_requirements.append({
                    "benefit_rule_id": None,
                    "evidence_items_json": items,
                    "description": raw[:300],
                    "auto_generated": True,
                    "review_status": "pending",
                    "confidence": conf,
                    "raw_text": raw[:2000],
                    "_clause_id": cid,
                })
                publish_targets.append("evidence_requirements")
                if pub_assessment == "draft_only":
                    pub_assessment = "publish_evidence_requirement"

        wants_draft = bool(
            benefit_key
            or exclusion_intent
            or has_cap
            or (hints and len(hints) > 0)
            or len(raw.strip()) >= 24
            or ats
            or fts_hint
            or fts_text
            or role_hints
            or dur_frag
        )
        if wants_draft:
            nums = hints.get("candidate_numeric_values") or []
            if not isinstance(nums, list):
                nums = []
            draft_rule_candidates.append(
                {
                    "clause_index": i,
                    "clause_id": cid,
                    "clause_type": ctype,
                    "candidate_category": theme_guess,
                    "candidate_service_key": benefit_key,
                    "candidate_coverage_status": cov_status,
                    "candidate_exclusion_flag": exclusion_intent,
                    "amount_fragments": {
                        "amount_value": amount_value,
                        "currency": currency if isinstance(currency, str) else None,
                        "amount_unit": amount_unit,
                        "numeric_values_hint": nums[:12],
                    },
                    "duration_quantity_fragments": dur_frag,
                    "applicability_fragments": {
                        "assignment_types": list(ats),
                        "family_status_terms": list(fts_hint) + fts_text,
                        "role_hints": role_hints,
                    },
                    "source_trace": {
                        "source_page_start": page_start,
                        "source_page_end": page_end,
                        "source_anchor": anchor,
                        "section_label": section,
                    },
                    "source_excerpt": raw[:500],
                    "confidence": conf,
                    "publishability_assessment": pub_assessment,
                    "publish_layer_targets": publish_targets,
                }
            )

    return {
        "benefit_rules": benefit_rules,
        "exclusions": exclusions,
        "evidence_requirements": evidence_requirements,
        "conditions": conditions,
        "assignment_applicability": assignment_applicability,
        "family_applicability": family_applicability,
        "source_links": source_links,
        "draft_rule_candidates": draft_rule_candidates,
    }


def _sanitize_benefit_rules_for_db(rules: List[Dict[str, Any]], request_id: Optional[str] = None) -> None:
    """Coerce calc_type and amount_value so INSERT never violates DB constraints."""
    for idx, r in enumerate(rules):
        ct = r.get("calc_type")
        if ct not in ALLOWED_CALC_TYPES:
            if request_id:
                log.warning(
                    "request_id=%s normalization sanitize benefit_rules[%s].calc_type %r -> other",
                    request_id,
                    idx,
                    ct,
                )
            r["calc_type"] = "other"
        av = r.get("amount_value")
        if av is not None:
            try:
                f = float(av)
                if math.isnan(f) or math.isinf(f):
                    r["amount_value"] = None
            except (TypeError, ValueError):
                r["amount_value"] = None


def run_normalization(
    db: Any,
    policy_document: Dict[str, Any],
    clauses: List[Dict[str, Any]],
    created_by: Optional[str] = None,
    request_id: Optional[str] = None,
    *,
    strict_require_conditions: bool = False,
) -> Dict[str, Any]:
    """
    Run full normalization: create/attach company_policy, create policy_version,
    persist benefit_rules, exclusions, evidence_requirements, conditions, applicability,
    and policy_source_links. Returns {policy_id, policy_version_id, summary}.
    The created policy_version is versioned (version_number) and traceable to the
    source document (source_policy_document_id) and to source clauses (policy_source_links).

    Layer 1 (document metadata) is used only for company_policies shell labels via
    layer1_fields_for_company_policy_shell. Clause hints are Layer-1 inputs transformed
    into Layer-2 rows (benefit_rules, exclusions, …) — see policy_pipeline_layers.

    Stages: extraction/clause load (caller) → clause mapping → readiness_eval → schema validation
    → persist company shell (if needed) → policy_version + children. Raises
    PolicyNormalizationPayloadInvalid for 422 when the draft is blocked, validation fails, or
    persistence fails. Auto-publish eligibility is returned as ``publishable``; callers run publish
    separately.
    """
    company_id = (policy_document.get("company_id") or "").strip() or None
    if not company_id:
        raise ValueError("Policy document has no company_id. Re-upload the document from the company's policy workspace.")
    doc_id = policy_document.get("id")
    doc_id_str = str(doc_id) if doc_id is not None else None
    shell = layer1_fields_for_company_policy_shell(
        policy_document.get("extracted_metadata"),
        filename=policy_document.get("filename"),
        version_label_row=policy_document.get("version_label"),
        effective_date_row=policy_document.get("effective_date"),
    )
    title = str(shell.get("title") or "Policy")[:200]
    version_label = shell.get("version")
    effective_date = shell.get("effective_date")

    # Build file_url from storage_path for company_policy (object key only, no bucket prefix)
    storage_path = policy_document.get("storage_path") or ""
    file_url = storage_path or ""

    log_extraction_and_normalization_shape(
        stage="load_input",
        request_id=request_id,
        document_id=doc_id_str,
        policy_document=policy_document,
        clauses=clauses,
    )

    policies = db.list_company_policies(company_id)
    need_new_company_policy = not policies
    if policies:
        policy_id = str(policies[0]["id"]) if policies[0].get("id") is not None else str(uuid.uuid4())
    else:
        policy_id = str(uuid.uuid4())

    # --- Stage: canonical mapping (no DB) ---
    result = normalize_clauses_to_objects(clauses, doc_id)
    _sanitize_benefit_rules_for_db(result.get("benefit_rules") or [], request_id=request_id)

    log_extraction_and_normalization_shape(
        stage="mapped_layer2",
        request_id=request_id,
        document_id=doc_id_str,
        policy_document=policy_document,
        clauses=clauses,
        normalized=result,
    )

    # --- Stage: readiness (draft gate vs auto-publish bar) ---
    readiness = evaluate_normalization_readiness(
        policy_document,
        result,
        strict_require_conditions=strict_require_conditions,
        request_id=request_id,
        document_id=doc_id_str,
    )
    if readiness.draft_blocked:
        log.warning(
            "request_id=%s policy_norm stage=normalization_blocked document_id=%s draft_block_count=%s fields=%s",
            request_id,
            doc_id_str,
            len(readiness.draft_block_details),
            [b.field for b in readiness.draft_block_details],
        )
        from .policy_processing_readiness import build_processing_readiness_envelope

        policy_readiness = build_processing_readiness_envelope(
            policy_document, clauses, result, readiness
        )
        raise PolicyNormalizationPayloadInvalid(
            error_code="NORMALIZATION_BLOCKED",
            message=(
                "Normalization cannot produce a meaningful draft: the document is not in a normalizable state "
                "(e.g. failed extraction), or policy scope is unknown and clause mapping produced no "
                "publish-layer benefits or exclusions."
            ),
            details=list(readiness.draft_block_details),
            document_id=doc_id_str,
            request_id=request_id,
            policy_readiness=policy_readiness,
            readiness_status=readiness.readiness_status,
            readiness_issues=list(readiness.readiness_issues),
            mapping_summary={
                "benefit_rules_count": len(result.get("benefit_rules") or []),
                "exclusions_count": len(result.get("exclusions") or []),
                "draft_rule_candidates_count": len(result.get("draft_rule_candidates") or []),
                "detected_document_type": policy_document.get("detected_document_type"),
                "detected_policy_scope": policy_document.get("detected_policy_scope"),
            },
        )

    existing = db.list_policy_versions(policy_id)
    version_number = max((v.get("version_number") or 1 for v in existing), default=1) + 1 if existing else 1

    version_id = str(uuid.uuid4())
    version_payload = build_version_payload_for_validation(
        version_id=version_id,
        policy_id=str(policy_id),
        doc_id=doc_id_str,
        version_number=version_number,
        status="auto_generated",
        auto_generated=True,
        review_status="pending",
        confidence=0.7,
    )

    log_extraction_and_normalization_shape(
        stage="pre_schema_validate",
        request_id=request_id,
        document_id=doc_id_str,
        policy_document=policy_document,
        clauses=clauses,
        normalized=result,
        version_payload_preview=version_payload,
    )

    # --- Stage: explicit schema validation (422, not 500) ---
    validate_policy_version_payload(version_payload, document_id=doc_id_str, request_id=request_id)
    validate_benefit_rules_payload(
        result.get("benefit_rules") or [], document_id=doc_id_str, request_id=request_id
    )
    validate_exclusions_payload(result.get("exclusions") or [], document_id=doc_id_str, request_id=request_id)
    validate_conditions_payload(result.get("conditions") or [], document_id=doc_id_str, request_id=request_id)

    preview = {
        "policy_versions": [version_payload],
        "benefit_rules_count": len(result.get("benefit_rules") or []),
        "exclusions_count": len(result.get("exclusions") or []),
        "conditions_count": len(result.get("conditions") or []),
    }
    log.info(
        "request_id=%s policy_norm stage=validated_ok document_id=%s diagnostic_preview=%s",
        request_id,
        doc_id_str,
        json_preview_for_diagnostics(preview, max_len=4000),
    )

    # --- Stage: persistence ---
    from .policy_normalization_states import (
        NORMALIZATION_STATE_COMPLETE,
        NORMALIZATION_STATE_DRAFT,
        NORMALIZATION_STATE_IN_PROGRESS,
    )

    final_normalization_state = NORMALIZATION_STATE_COMPLETE if readiness.publishable else NORMALIZATION_STATE_DRAFT

    from .policy_processing_readiness import build_processing_readiness_envelope
    from .policy_normalization_draft import build_normalization_draft_model

    policy_readiness = build_processing_readiness_envelope(
        policy_document, clauses, result, readiness
    )
    normalization_draft = build_normalization_draft_model(
        policy_document=policy_document,
        company_id=company_id,
        policy_id=str(policy_id),
        policy_version_id=version_id,
        clauses=clauses,
        mapped=result,
        norm_core=readiness,
    )

    def _source_link_for_clause(
        conn: Any, clause_id: Optional[str], obj_type: str, obj_id: str
    ) -> None:
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
                db.insert_policy_source_link(link, connection=conn)
                return

    def _persist_normalization_bundle(conn: Any) -> None:
        if need_new_company_policy:
            db.create_company_policy(
                policy_id=policy_id,
                company_id=company_id,
                title=title[:200],
                version=version_label,
                effective_date=effective_date,
                file_url=file_url or "policy-document",
                file_type=policy_document.get("mime_type", "").split("/")[-1] or "pdf",
                created_by=created_by,
                request_id=request_id,
                connection=conn,
            )

        db.create_policy_version(
            version_id=version_id,
            policy_id=str(policy_id),
            source_policy_document_id=doc_id_str,
            version_number=version_number,
            status="auto_generated",
            auto_generated=True,
            review_status="pending",
            confidence=0.7,
            created_by=created_by,
            request_id=request_id,
            normalization_state=NORMALIZATION_STATE_IN_PROGRESS,
            connection=conn,
        )

        bmap: Dict[int, str] = {}

        for r in result["benefit_rules"]:
            r["policy_version_id"] = version_id
            rid = db.insert_policy_benefit_rule(r, connection=conn)
            idx = r.get("_clause_idx")
            if idx is not None:
                bmap[idx] = rid

        exclusion_ids: List[Tuple[str, str]] = []
        evidence_ids: List[Tuple[str, str]] = []

        for excl in result["exclusions"]:
            excl["policy_version_id"] = version_id
            eid = db.insert_policy_exclusion(excl, connection=conn)
            exclusion_ids.append((eid, excl.get("_clause_id")))

        for ev in result["evidence_requirements"]:
            ev["policy_version_id"] = version_id
            evid = db.insert_policy_evidence_requirement(ev, connection=conn)
            evidence_ids.append((evid, ev.get("_clause_id")))

        first_benefit_id = next(iter(bmap.values()), None)
        for c in result["conditions"]:
            c["policy_version_id"] = version_id
            idx = c.get("_benefit_clause_idx")
            if idx is not None and idx in bmap:
                c["object_id"] = bmap[idx]
            elif first_benefit_id:
                c["object_id"] = first_benefit_id
            else:
                continue
            db.insert_policy_rule_condition(c, connection=conn)

        for a in result["assignment_applicability"]:
            idx = a.get("_benefit_clause_idx")
            if idx is not None and idx in bmap:
                a["policy_version_id"] = version_id
                a["benefit_rule_id"] = bmap[idx]
                db.insert_policy_assignment_applicability(a, connection=conn)

        for f in result["family_applicability"]:
            idx = f.get("_benefit_clause_idx")
            if idx is not None and idx in bmap:
                f["policy_version_id"] = version_id
                f["benefit_rule_id"] = bmap[idx]
                db.insert_policy_family_applicability(f, connection=conn)

        for r in result["benefit_rules"]:
            idx = r.get("_clause_idx")
            cid = r.get("_clause_id")
            if idx is not None and idx in bmap and cid:
                _source_link_for_clause(conn, cid, "benefit_rule", bmap[idx])

        for eid, cid in exclusion_ids:
            _source_link_for_clause(conn, cid, "exclusion", eid)

        for evid, cid in evidence_ids:
            _source_link_for_clause(conn, cid, "evidence_requirement", evid)

        db.update_policy_version_normalization_draft(
            version_id,
            normalization_draft,
            request_id=request_id,
            normalization_state=final_normalization_state,
            connection=conn,
        )

    if request_id:
        log.info(
            "request_id=%s policy_norm stage=persist_start company_id=%s doc_id=%s policy_id=%s version_id=%s publishable=%s",
            request_id,
            company_id,
            doc_id_str,
            policy_id,
            version_id,
            readiness.publishable,
        )

    if not hasattr(db, "run_policy_normalization_transaction"):
        raise PolicyNormalizationPayloadInvalid(
            error_code="PERSISTENCE_FAILED",
            message="Database adapter does not support atomic normalization transactions.",
            details=[
                PolicyNormalizationFieldIssue(
                    field="database",
                    issue="missing run_policy_normalization_transaction",
                    actual="incompatible_db",
                )
            ],
            document_id=doc_id_str,
            request_id=request_id,
            persistence_stage="normalization_transaction",
        )

    try:
        db.run_policy_normalization_transaction(_persist_normalization_bundle)
    except (IntegrityError, OperationalError) as persist_exc:
        log.warning(
            "request_id=%s policy_norm stage=persist_bundle_failed document_id=%s exc_type=%s exc_msg=%s",
            request_id,
            doc_id_str,
            type(persist_exc).__name__,
            str(persist_exc)[:400],
            exc_info=True,
        )
        raise PolicyNormalizationPayloadInvalid(
            error_code="PERSISTENCE_FAILED",
            message="Database rejected normalization (company policy, version, Layer-2, or draft) — transaction rolled back.",
            details=[
                PolicyNormalizationFieldIssue(
                    field="normalization_bundle",
                    issue=str(getattr(persist_exc, "orig", persist_exc))[:800],
                    actual=type(persist_exc).__name__,
                )
            ],
            document_id=doc_id_str,
            request_id=request_id,
            persistence_stage="normalization_transaction",
        ) from persist_exc

    if request_id:
        log.info(
            "request_id=%s policy_norm stage=persist_ok document_id=%s policy_id=%s policy_version_id=%s publishable=%s normalization_state=%s",
            request_id,
            doc_id_str,
            policy_id,
            version_id,
            readiness.publishable,
            final_normalization_state,
        )

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
        "normalized": True,
        "normalization_state": final_normalization_state,
        "publishable": readiness.publishable,
        "readiness_status": readiness.readiness_status,
        "readiness_issues": [i.to_json() for i in readiness.readiness_issues],
        "policy_readiness": policy_readiness,
        "normalization_draft": normalization_draft,
        "summary": {
            "benefit_rules": len(result["benefit_rules"]),
            "exclusions": len(result["exclusions"]),
            "evidence_requirements": len(result["evidence_requirements"]),
            "conditions": len(result["conditions"]),
            "draft_rule_candidates": len(result.get("draft_rule_candidates") or []),
            "by_category": by_category,
        },
    }
