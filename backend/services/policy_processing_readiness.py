"""
Three-tier policy processing readiness: normalization vs publish vs employee comparison.

Used by normalize responses, HR review payloads, and diagnostics so we never conflate
“draft saved”, “publishable”, and “comparison engine ready”.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .policy_comparison_readiness import (
    EMPLOYEE_COMPARISON_REQUIRED_BENEFIT_KEYS,
    benefit_rule_has_decision_signal,
)
from .policy_document_intake import DOC_TYPE_POLICY_SUMMARY
from .policy_normalization_validate import NormalizationReadinessResult

# --- Suggested issue codes (stable API strings) ---
MISSING_DOCUMENT_TYPE = "MISSING_DOCUMENT_TYPE"
MISSING_SCOPE = "MISSING_SCOPE"
NO_CLAUSE_CANDIDATES = "NO_CLAUSE_CANDIDATES"
NO_LAYER2_RULES = "NO_LAYER2_RULES"
NO_PUBLISHABLE_BENEFITS_OR_EXCLUSIONS = "NO_PUBLISHABLE_BENEFITS_OR_EXCLUSIONS"
NO_CANONICAL_SERVICE_MATCH = "NO_CANONICAL_SERVICE_MATCH"
NO_STRUCTURED_LIMITS = "NO_STRUCTURED_LIMITS"
ONLY_SUMMARY_LEVEL_SIGNALS = "ONLY_SUMMARY_LEVEL_SIGNALS"
COVERAGE_ONLY_NO_CAPS = "COVERAGE_ONLY_NO_CAPS"
READY_FOR_DRAFT_ONLY = "READY_FOR_DRAFT_ONLY"
READY_FOR_PUBLISH = "READY_FOR_PUBLISH"
READY_FOR_COMPARISON = "READY_FOR_COMPARISON"
SOURCE_DOCUMENT_FAILED = "SOURCE_DOCUMENT_FAILED"
APPLICABILITY_INSUFFICIENT = "APPLICABILITY_INSUFFICIENT"


ReadinessStatus = str  # "ready" | "partial" | "not_ready"


@dataclass
class ReadinessIssue:
    code: str
    message: str
    field: Optional[str] = None

    def to_json(self) -> Dict[str, Any]:
        o: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.field:
            o["field"] = self.field
        return o


@dataclass
class ReadinessSlice:
    status: ReadinessStatus
    issues: List[ReadinessIssue] = field(default_factory=list)

    def to_json(self) -> Dict[str, Any]:
        return {"status": self.status, "issues": [i.to_json() for i in self.issues]}


def policy_readiness_envelope_dict(
    normalization: ReadinessSlice,
    publish: ReadinessSlice,
    comparison: ReadinessSlice,
) -> Dict[str, Any]:
    return {
        "normalization_readiness": normalization.to_json(),
        "publish_readiness": publish.to_json(),
        "comparison_readiness": comparison.to_json(),
    }


def _infer_document_type(policy_document: Dict[str, Any]) -> Optional[str]:
    t = (policy_document.get("detected_document_type") or "").strip()
    if t:
        return t
    em = policy_document.get("extracted_metadata")
    if isinstance(em, dict):
        for k in ("document_type", "detected_document_type", "policy_document_type"):
            v = em.get(k)
            if v and str(v).strip():
                return str(v).strip()
    return None


def _infer_scope(policy_document: Dict[str, Any]) -> Optional[str]:
    s = (policy_document.get("detected_policy_scope") or "").strip()
    if s and s.lower() != "unknown":
        return s
    em = policy_document.get("extracted_metadata")
    if isinstance(em, dict):
        for k in ("policy_scope", "detected_policy_scope"):
            v = em.get(k)
            if v and str(v).strip() and str(v).strip().lower() != "unknown":
                return str(v).strip()
    return None


def _clause_candidate_count(clauses: Sequence[Dict[str, Any]]) -> int:
    n = 0
    for c in clauses:
        if not isinstance(c, dict):
            continue
        raw = (c.get("raw_text") or "").strip()
        hints = c.get("normalized_hint_json")
        if raw or (isinstance(hints, dict) and len(hints) > 0):
            n += 1
    return n


def _canonical_comparison_bucket(benefit_key: str) -> Optional[str]:
    k = (benefit_key or "").strip().lower().replace("-", "_")
    if k in ("temporary_housing", "housing"):
        return "temporary_housing"
    if k in ("schooling", "schools", "school"):
        return "schooling"
    if k in ("shipment", "movers", "moving"):
        return "shipment"
    if k in ("banking_setup", "banks", "bank"):
        return "banking_setup"
    if k in ("insurance", "insurances"):
        return "insurance"
    return None


def _monetary_structured(rule: Dict[str, Any]) -> bool:
    ct = (rule.get("calc_type") or "").strip()
    if ct == "percent_salary":
        return rule.get("amount_value") is not None
    if ct in ("flat_amount", "reimbursement", "difference_only", "per_diem", "unit_cap", "other"):
        av = rule.get("amount_value")
        if av is None:
            return False
        try:
            if float(av) <= 0:
                return False
        except (TypeError, ValueError):
            return False
        if ct == "flat_amount" and not (rule.get("currency") or "").strip():
            return False
        if ct == "unit_cap":
            if not (rule.get("amount_unit") or "").strip():
                return False
        return True
    return benefit_rule_has_decision_signal(rule)


def _applicability_ok(
    benefit_rules: Sequence[Dict[str, Any]],
    assignment_applicability: Sequence[Dict[str, Any]],
    conditions: Sequence[Dict[str, Any]],
) -> bool:
    if not benefit_rules:
        return True
    if assignment_applicability:
        return True
    for c in conditions:
        if (c.get("object_type") or "") == "benefit_rule":
            return True
    return False


def evaluate_normalization_readiness_slice(
    policy_document: Dict[str, Any],
    clauses: Sequence[Dict[str, Any]],
    normalized: Dict[str, Any],
    norm_core: NormalizationReadinessResult,
) -> ReadinessSlice:
    issues: List[ReadinessIssue] = []
    processing_failed = (policy_document.get("processing_status") or "").lower() == "failed"
    cc = _clause_candidate_count(clauses)
    dtype = _infer_document_type(policy_document)
    scope = _infer_scope(policy_document)
    benefits = normalized.get("benefit_rules") or []
    exclusions = normalized.get("exclusions") or []
    has_layer2 = len(benefits) > 0 or len(exclusions) > 0

    if processing_failed:
        issues.append(
            ReadinessIssue(
                code=SOURCE_DOCUMENT_FAILED,
                message="Document processing failed; not suitable for normalized draft creation.",
                field="document.processing_status",
            )
        )
        return ReadinessSlice(status="not_ready", issues=issues)
    if cc == 0:
        issues.append(
            ReadinessIssue(
                code=NO_CLAUSE_CANDIDATES,
                message="No clause rows with text or extraction hints; reprocess the document.",
                field="clauses",
            )
        )
        return ReadinessSlice(status="not_ready", issues=issues)
    if not dtype:
        issues.append(
            ReadinessIssue(
                code=MISSING_DOCUMENT_TYPE,
                message="No document classification on the policy row or extracted metadata.",
                field="document.detected_document_type",
            )
        )
    if norm_core.draft_blocked:
        if not scope and not has_layer2:
            issues.append(
                ReadinessIssue(
                    code=MISSING_SCOPE,
                    message="Policy scope is unknown and no benefit or exclusion rows were mapped.",
                    field="document.detected_policy_scope",
                )
            )
            issues.append(
                ReadinessIssue(
                    code=NO_LAYER2_RULES,
                    message="No mapped Layer-2 rows and insufficient metadata to anchor a draft.",
                    field="policy_versions[0].layer2_structure",
                )
            )
        return ReadinessSlice(status="not_ready", issues=issues)

    if not dtype:
        return ReadinessSlice(
            status="partial",
            issues=issues
            + [
                ReadinessIssue(
                    code=READY_FOR_DRAFT_ONLY,
                    message="Draft normalization can proceed but document type should be confirmed after classify/reprocess.",
                )
            ],
        )

    if not has_layer2:
        summary_only = (policy_document.get("detected_document_type") or "").strip() == DOC_TYPE_POLICY_SUMMARY
        extra: List[ReadinessIssue] = [
            ReadinessIssue(
                code=ONLY_SUMMARY_LEVEL_SIGNALS,
                message=(
                    "policy_summary documents often stay narrative-only until a full policy is uploaded."
                    if summary_only
                    else "Clauses did not map to benefit or exclusion rows (common for policy summaries)."
                ),
                field="document.detected_document_type" if summary_only else None,
            ),
            ReadinessIssue(
                code=READY_FOR_DRAFT_ONLY,
                message="Enough structure to persist a draft policy version; enrich Layer 2 for publish.",
            ),
        ]
        return ReadinessSlice(status="partial", issues=extra)

    ready_issues = list(issues)
    ready_issues.append(
        ReadinessIssue(
            code=READY_FOR_DRAFT_ONLY,
            message="Normalized draft includes Layer-2 benefit and/or exclusion rows.",
        )
    )
    return ReadinessSlice(status="ready", issues=ready_issues)


def evaluate_publish_readiness_slice(
    policy_document: Dict[str, Any],
    normalized: Dict[str, Any],
    norm_core: NormalizationReadinessResult,
) -> ReadinessSlice:
    issues: List[ReadinessIssue] = []
    benefits = normalized.get("benefit_rules") or []
    exclusions = normalized.get("exclusions") or []
    empty_layer2 = len(benefits) == 0 and len(exclusions) == 0
    processing_failed = (policy_document.get("processing_status") or "").lower() == "failed"

    if processing_failed:
        issues.append(
            ReadinessIssue(
                code=SOURCE_DOCUMENT_FAILED,
                message="Publish is blocked while the source document is in a failed state.",
                field="document.processing_status",
            )
        )
        return ReadinessSlice(status="not_ready", issues=issues)
    if norm_core.draft_blocked:
        issues.append(
            ReadinessIssue(
                code=NO_PUBLISHABLE_BENEFITS_OR_EXCLUSIONS,
                message="Publish gate requires at least one benefit rule or exclusion.",
            )
        )
        return ReadinessSlice(status="not_ready", issues=issues)
    if empty_layer2:
        issues.append(
            ReadinessIssue(
                code=NO_PUBLISHABLE_BENEFITS_OR_EXCLUSIONS,
                message="No benefit rules or exclusions; cannot satisfy employee publish gate.",
                field="policy_versions[0].layer2_structure",
            )
        )
        return ReadinessSlice(status="not_ready", issues=issues)
    if not norm_core.publishable:
        issues.append(
            ReadinessIssue(
                code=COVERAGE_ONLY_NO_CAPS,
                message="Structured rows exist but auto-publish requirements are not met (e.g. strict conditions).",
            )
        )
        return ReadinessSlice(status="partial", issues=issues)
    issues.append(
        ReadinessIssue(
            code=READY_FOR_PUBLISH,
            message="Layer-2 output satisfies current auto-publish / publish-gate structure.",
        )
    )
    return ReadinessSlice(status="ready", issues=issues)


def evaluate_comparison_readiness_slice(
    normalized: Dict[str, Any],
    *,
    assignment_applicability: Optional[Sequence[Dict[str, Any]]] = None,
    conditions: Optional[Sequence[Dict[str, Any]]] = None,
) -> ReadinessSlice:
    issues: List[ReadinessIssue] = []
    rules: List[Dict[str, Any]] = list(normalized.get("benefit_rules") or [])
    app = assignment_applicability or normalized.get("assignment_applicability") or []
    cond = conditions or normalized.get("conditions") or []

    if not rules:
        issues.append(
            ReadinessIssue(
                code=NO_CANONICAL_SERVICE_MATCH,
                message="Employee service comparison expects at least one benefit_rule row mapped to a service category.",
            )
        )
        return ReadinessSlice(status="not_ready", issues=issues)

    buckets_with_rule: set[str] = set()
    buckets_with_signal: set[str] = set()
    buckets_structured: set[str] = set()
    for r in rules:
        bk = (r.get("benefit_key") or "").strip()
        bucket = _canonical_comparison_bucket(bk)
        if not bucket:
            continue
        buckets_with_rule.add(bucket)
        if benefit_rule_has_decision_signal(r):
            buckets_with_signal.add(bucket)
        if _monetary_structured(r):
            buckets_structured.add(bucket)
        elif benefit_rule_has_decision_signal(r):
            buckets_structured.add(bucket)

    if not buckets_with_rule:
        issues.append(
            ReadinessIssue(
                code=NO_CANONICAL_SERVICE_MATCH,
                message="No benefit rules use keys that map to employee service categories (housing, schools, movers, etc.).",
            )
        )
        return ReadinessSlice(status="not_ready", issues=issues)

    missing_req = [k for k in sorted(EMPLOYEE_COMPARISON_REQUIRED_BENEFIT_KEYS) if k not in buckets_with_rule]
    missing_signal = [k for k in sorted(EMPLOYEE_COMPARISON_REQUIRED_BENEFIT_KEYS) if k in buckets_with_rule and k not in buckets_with_signal]
    missing_structure = [
        k
        for k in sorted(EMPLOYEE_COMPARISON_REQUIRED_BENEFIT_KEYS)
        if k in buckets_with_rule and k not in buckets_structured
    ]
    app_ok = _applicability_ok(rules, app, cond)

    fully_ready = (
        not missing_req
        and not missing_signal
        and not missing_structure
        and app_ok
    )
    if fully_ready:
        return ReadinessSlice(
            status="ready",
            issues=[
                ReadinessIssue(
                    code=READY_FOR_COMPARISON,
                    message="Core comparison categories (housing, schooling, shipment) have usable limits for the wizard engine.",
                )
            ],
        )

    if not buckets_with_signal:
        return ReadinessSlice(
            status="partial",
            issues=[
                ReadinessIssue(
                    code=NO_STRUCTURED_LIMITS,
                    message="Service-mapped benefit rules exist but lack caps, amounts, or approval signals the comparison engine can use.",
                )
            ],
        )

    if missing_req:
        issues.append(
            ReadinessIssue(
                code=COVERAGE_ONLY_NO_CAPS,
                message=f"Comparison categories missing entirely: {', '.join(missing_req)}.",
            )
        )
    if missing_signal:
        issues.append(
            ReadinessIssue(
                code=NO_STRUCTURED_LIMITS,
                message=f"Rules lack decision signals for: {', '.join(missing_signal)}.",
            )
        )
    if missing_structure:
        issues.append(
            ReadinessIssue(
                code=NO_STRUCTURED_LIMITS,
                message=f"Monetary/unit structure incomplete (e.g. currency or unit) for: {', '.join(missing_structure)}.",
            )
        )
    if not app_ok:
        issues.append(
            ReadinessIssue(
                code=APPLICABILITY_INSUFFICIENT,
                message="Add assignment applicability or benefit-linked conditions so comparisons can scope rules.",
                field="policy_assignment_applicability",
            )
        )
    return ReadinessSlice(status="partial", issues=issues)


def build_processing_readiness_envelope(
    policy_document: Dict[str, Any],
    clauses: Sequence[Dict[str, Any]],
    normalized: Dict[str, Any],
    norm_core: NormalizationReadinessResult,
) -> Dict[str, Any]:
    n_slice = evaluate_normalization_readiness_slice(policy_document, clauses, normalized, norm_core)
    p_slice = evaluate_publish_readiness_slice(policy_document, normalized, norm_core)
    c_slice = evaluate_comparison_readiness_slice(normalized)
    env = policy_readiness_envelope_dict(n_slice, p_slice, c_slice)
    try:
        from .policy_rule_comparison_readiness import evaluate_policy_comparison_readiness

        rc = evaluate_policy_comparison_readiness(normalized=normalized)
        env["comparison_rule_readiness"] = {
            "policy_level": rc["policy_level"],
            "per_benefit_key": rc["per_benefit_key"],
            "counts_by_level": rc["counts_by_level"],
            "supports_any_budget_delta": rc["supports_any_budget_delta"],
            "comparison_ready_strict": rc["comparison_ready_strict"],
        }
    except Exception:
        pass
    return env


def evaluate_stored_policy_readiness(
    *,
    latest_version: Optional[Dict[str, Any]],
    published_version: Optional[Dict[str, Any]],
    benefit_rules: List[Dict[str, Any]],
    exclusions: List[Dict[str, Any]],
    conditions: List[Dict[str, Any]],
    assignment_applicability: List[Dict[str, Any]],
    source_document: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    HR review / GET normalized: readiness for whatever is loaded as the latest version matrix.
    Publish tier prefers published_version row state; comparison uses the same benefit_rules passed in
    (typically latest — caller may pass published rules if desired).
    """
    if not latest_version:
        nr = ReadinessSlice(
            status="not_ready",
            issues=[
                ReadinessIssue(
                    code=NO_LAYER2_RULES,
                    message="No policy version exists yet; normalize a document first.",
                )
            ],
        )
        pr = ReadinessSlice(status="not_ready", issues=list(nr.issues))
        cr = ReadinessSlice(
            status="not_ready",
            issues=[
                ReadinessIssue(
                    code=NO_CANONICAL_SERVICE_MATCH,
                    message="No normalized benefit rules loaded.",
                )
            ],
        )
        return policy_readiness_envelope_dict(nr, pr, cr)

    normalized = {
        "benefit_rules": benefit_rules,
        "exclusions": exclusions,
        "conditions": conditions,
        "assignment_applicability": assignment_applicability,
    }
    empty_layer2 = len(benefit_rules) == 0 and len(exclusions) == 0
    doc_failed = source_document is not None and (source_document.get("processing_status") or "").lower() == "failed"

    n_issues: List[ReadinessIssue] = []
    if empty_layer2:
        n_issues = [
            ReadinessIssue(
                code=ONLY_SUMMARY_LEVEL_SIGNALS,
                message="Latest version has no benefit or exclusion rows.",
            ),
            ReadinessIssue(code=READY_FOR_DRAFT_ONLY, message="Draft shell exists; add or map Layer-2 content."),
        ]
        n_slice = ReadinessSlice(status="partial", issues=n_issues)
    else:
        n_slice = ReadinessSlice(
            status="ready",
            issues=[
                ReadinessIssue(
                    code=READY_FOR_DRAFT_ONLY,
                    message="Latest version includes Layer-2 rows.",
                )
            ],
        )

    if doc_failed:
        p_slice = ReadinessSlice(
            status="not_ready",
            issues=[
                ReadinessIssue(
                    code=SOURCE_DOCUMENT_FAILED,
                    message="Linked source document failed processing; fix before publish.",
                    field="document.processing_status",
                )
            ],
        )
    elif empty_layer2:
        p_slice = ReadinessSlice(
            status="not_ready",
            issues=[
                ReadinessIssue(
                    code=NO_PUBLISHABLE_BENEFITS_OR_EXCLUSIONS,
                    message="Cannot publish without at least one benefit rule or exclusion.",
                )
            ],
        )
    else:
        pub = published_version or {}
        is_published = (pub.get("status") or "").lower() == "published"
        if is_published:
            p_slice = ReadinessSlice(
                status="ready",
                issues=[ReadinessIssue(code=READY_FOR_PUBLISH, message="A published version is active for employees.")],
            )
        else:
            p_slice = ReadinessSlice(
                status="partial",
                issues=[
                    ReadinessIssue(
                        code=READY_FOR_DRAFT_ONLY,
                        message="Layer-2 data exists but no published version yet; use Publish in HR review.",
                    )
                ],
            )

    c_slice = evaluate_comparison_readiness_slice(
        normalized,
        assignment_applicability=assignment_applicability,
        conditions=conditions,
    )

    env = policy_readiness_envelope_dict(n_slice, p_slice, c_slice)
    try:
        from .policy_rule_comparison_readiness import evaluate_policy_comparison_readiness

        rc = evaluate_policy_comparison_readiness(normalized=normalized)
        env["comparison_rule_readiness"] = {
            "policy_level": rc["policy_level"],
            "per_benefit_key": rc["per_benefit_key"],
            "counts_by_level": rc["counts_by_level"],
            "supports_any_budget_delta": rc["supports_any_budget_delta"],
            "comparison_ready_strict": rc["comparison_ready_strict"],
        }
    except Exception:
        pass
    return env
