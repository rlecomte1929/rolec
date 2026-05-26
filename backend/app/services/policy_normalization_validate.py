"""
Pre-DB validation and readiness checks for policy normalization.

Validates assembled Layer-2 payloads before persistence so failures return 422 with field paths,
not opaque 500s from the database driver.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .policy_document_intake import DOC_TYPE_POLICY_SUMMARY
from .policy_normalization_errors import PolicyNormalizationFieldIssue, PolicyNormalizationPayloadInvalid

# Must match policy_normalization.ALLOWED_CALC_TYPES and DB check on policy_benefit_rules.calc_type
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

log = logging.getLogger(__name__)

ALLOWED_VERSION_STATUSES = frozenset(
    {
        "draft",
        "auto_generated",
        "in_review",
        "approved",
        "archived",
        "review_required",
        "reviewed",
        "published",
    }
)
ALLOWED_REVIEW_STATUSES = frozenset({"pending", "accepted", "rejected", "edited"})
ALLOWED_CONDITION_TYPES = frozenset(
    {
        "assignment_type",
        "family_status",
        "duration_threshold",
        "accompanied_family",
        "localization_exclusion",
        "remote_location",
        "school_age_threshold",
        "other",
    }
)
ALLOWED_OBJECT_TYPES = frozenset({"benefit_rule", "exclusion", "evidence_requirement"})
ALLOWED_EXCLUSION_DOMAINS = frozenset({"scope", "tax", "benefit"})


class PolicyVersionPayloadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    source_policy_document_id: Optional[str] = None
    version_number: int = Field(ge=1)
    status: str
    auto_generated: bool = True
    review_status: str = "pending"
    confidence: Optional[float] = None

    @field_validator("status")
    @classmethod
    def status_ok(cls, v: str) -> str:
        s = (v or "").strip()
        if s not in ALLOWED_VERSION_STATUSES:
            raise ValueError(f"status must be one of {sorted(ALLOWED_VERSION_STATUSES)}")
        return s

    @field_validator("review_status")
    @classmethod
    def review_ok(cls, v: str) -> str:
        s = (v or "").strip()
        if s not in ALLOWED_REVIEW_STATUSES:
            raise ValueError(f"review_status must be one of {sorted(ALLOWED_REVIEW_STATUSES)}")
        return s


class BenefitRulePayloadModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    benefit_key: str = Field(min_length=1)
    benefit_category: str = Field(min_length=1)
    calc_type: Optional[str] = None
    amount_value: Optional[float] = None
    amount_unit: Optional[str] = None
    currency: Optional[str] = None
    frequency: Optional[str] = None

    @field_validator("calc_type")
    @classmethod
    def calc_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_CALC_TYPES:
            raise ValueError(f"calc_type must be one of {sorted(ALLOWED_CALC_TYPES)}")
        return v

    @field_validator("amount_value")
    @classmethod
    def amount_finite(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        import math

        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            raise ValueError("amount_value must be a finite number")
        return v


class ExclusionPayloadModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    domain: str
    benefit_key: Optional[str] = None
    description: Optional[str] = None

    @field_validator("domain")
    @classmethod
    def domain_ok(cls, v: str) -> str:
        s = (v or "").strip()
        if s not in ALLOWED_EXCLUSION_DOMAINS:
            raise ValueError(f"domain must be one of {sorted(ALLOWED_EXCLUSION_DOMAINS)}")
        return s


class ConditionPayloadModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    object_type: str
    condition_type: str
    condition_value_json: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("object_type")
    @classmethod
    def ot_ok(cls, v: str) -> str:
        s = (v or "").strip()
        if s not in ALLOWED_OBJECT_TYPES:
            raise ValueError(f"object_type must be one of {sorted(ALLOWED_OBJECT_TYPES)}")
        return s

    @field_validator("condition_type")
    @classmethod
    def ct_ok(cls, v: str) -> str:
        s = (v or "").strip()
        if s not in ALLOWED_CONDITION_TYPES:
            raise ValueError(f"condition_type must be one of {sorted(ALLOWED_CONDITION_TYPES)}")
        return s


def _pydantic_issues_to_field_issues(
    errors: Sequence[Any], prefix: str = ""
) -> List[PolicyNormalizationFieldIssue]:
    out: List[PolicyNormalizationFieldIssue] = []
    for e in errors:
        if isinstance(e, dict):
            loc = e.get("loc") or ()
            msg = str(e.get("msg", "validation error"))
            ctx = e.get("ctx") if isinstance(e.get("ctx"), dict) else {}
        else:
            loc = getattr(e, "loc", ()) or ()
            msg = str(getattr(e, "msg", e))
            ctx = getattr(e, "ctx", None) or {}
        parts = [str(p) for p in loc if p not in ("body",)]
        field_path = prefix + (".".join(parts) if parts else "payload")
        expected = str(ctx["expected"]) if ctx.get("expected") is not None else None
        actual = str(ctx["actual"]) if ctx.get("actual") is not None else None
        out.append(
            PolicyNormalizationFieldIssue(
                field=field_path,
                issue=msg,
                expected=expected,
                actual=actual,
            )
        )
    return out


def validate_policy_version_payload(
    payload: Dict[str, Any],
    *,
    document_id: Optional[str],
    request_id: Optional[str],
) -> None:
    from pydantic import ValidationError

    try:
        PolicyVersionPayloadModel.model_validate(payload)
    except ValidationError as e:
        issues = _pydantic_issues_to_field_issues(e.errors(), "policy_versions[0].")
        raise PolicyNormalizationPayloadInvalid(
            error_code="INVALID_POLICY_VERSION_SCHEMA",
            message="Schema validation failed on assembled policy_versions row (internal mapping or taxonomy inconsistency), not weak document extraction.",
            details=issues,
            document_id=document_id,
            request_id=request_id,
        ) from e


def validate_benefit_rules_payload(
    rules: List[Dict[str, Any]],
    *,
    document_id: Optional[str],
    request_id: Optional[str],
) -> None:
    from pydantic import ValidationError

    for i, r in enumerate(rules):
        public = {k: v for k, v in r.items() if not str(k).startswith("_")}
        try:
            BenefitRulePayloadModel.model_validate(public)
        except ValidationError as e:
            issues = _pydantic_issues_to_field_issues(e.errors(), f"policy_versions[0].benefit_rules[{i}].")
            raise PolicyNormalizationPayloadInvalid(
                error_code="INVALID_POLICY_VERSION_SCHEMA",
                message="Schema validation failed on a mapped benefit rule row.",
                details=issues,
                document_id=document_id,
                request_id=request_id,
            ) from e


def validate_exclusions_payload(
    exclusions: List[Dict[str, Any]],
    *,
    document_id: Optional[str],
    request_id: Optional[str],
) -> None:
    from pydantic import ValidationError

    for i, ex in enumerate(exclusions):
        public = {k: v for k, v in ex.items() if not str(k).startswith("_")}
        try:
            ExclusionPayloadModel.model_validate(public)
        except ValidationError as e:
            issues = _pydantic_issues_to_field_issues(e.errors(), f"policy_versions[0].exclusions[{i}].")
            raise PolicyNormalizationPayloadInvalid(
                error_code="INVALID_POLICY_VERSION_SCHEMA",
                message="Schema validation failed on a mapped exclusion row.",
                details=issues,
                document_id=document_id,
                request_id=request_id,
            ) from e


def validate_conditions_payload(
    conditions: List[Dict[str, Any]],
    *,
    document_id: Optional[str],
    request_id: Optional[str],
) -> None:
    from pydantic import ValidationError

    for i, c in enumerate(conditions):
        public = {
            "object_type": c.get("object_type"),
            "condition_type": c.get("condition_type"),
            "condition_value_json": c.get("condition_value_json") or {},
        }
        if not isinstance(public["condition_value_json"], dict):
            raise PolicyNormalizationPayloadInvalid(
                error_code="INVALID_POLICY_VERSION_SCHEMA",
                message="Schema validation failed: condition_value_json must be an object.",
                details=[
                    PolicyNormalizationFieldIssue(
                        field=f"policy_versions[0].conditions[{i}].condition_value_json",
                        issue="expected object, got "
                        + type(public["condition_value_json"]).__name__,
                        expected="object",
                        actual=type(public["condition_value_json"]).__name__,
                    )
                ],
                document_id=document_id,
                request_id=request_id,
            )
        try:
            ConditionPayloadModel.model_validate(public)
        except ValidationError as e:
            issues = _pydantic_issues_to_field_issues(e.errors(), f"policy_versions[0].conditions[{i}].")
            raise PolicyNormalizationPayloadInvalid(
                error_code="INVALID_POLICY_VERSION_SCHEMA",
                message="Schema validation failed on a mapped condition row.",
                details=issues,
                document_id=document_id,
                request_id=request_id,
            ) from e


def log_extraction_and_normalization_shape(
    *,
    stage: str,
    request_id: Optional[str],
    document_id: Optional[str],
    policy_document: Dict[str, Any],
    clauses: Sequence[Dict[str, Any]],
    normalized: Optional[Dict[str, Any]] = None,
    version_payload_preview: Optional[Dict[str, Any]] = None,
) -> None:
    """Structured, grep-friendly logs (no raw document text)."""
    doc_keys = sorted(policy_document.keys()) if isinstance(policy_document, dict) else []
    em = policy_document.get("extracted_metadata")
    em_keys = sorted(em.keys()) if isinstance(em, dict) else []
    det_type = policy_document.get("detected_document_type")
    det_scope = policy_document.get("detected_policy_scope")
    clause_types: Dict[str, int] = {}
    for c in clauses:
        ct = str(c.get("clause_type") or "unknown")
        clause_types[ct] = clause_types.get(ct, 0) + 1
    hint_keys_sample: List[str] = []
    for c in clauses[:3]:
        h = c.get("normalized_hint_json")
        if isinstance(h, dict) and h:
            hint_keys_sample.extend(list(h.keys())[:8])

    extra_norm = ""
    if normalized:
        extra_norm = (
            f" benefit_rules={len(normalized.get('benefit_rules') or [])}"
            f" exclusions={len(normalized.get('exclusions') or [])}"
            f" evidence={len(normalized.get('evidence_requirements') or [])}"
            f" conditions={len(normalized.get('conditions') or [])}"
        )
    extra_vp = ""
    if version_payload_preview:
        extra_vp = f" version_status={version_payload_preview.get('status')!r} vn={version_payload_preview.get('version_number')}"

    log.info(
        "request_id=%s policy_norm stage=%s document_id=%s detected_document_type=%s detected_policy_scope=%s "
        "doc_top_keys=%s extracted_metadata_keys=%s clauses_count=%s clause_type_counts=%s hint_keys_sample=%s%s%s",
        request_id,
        stage,
        document_id,
        det_type,
        det_scope,
        doc_keys[:40],
        em_keys[:40],
        len(clauses),
        clause_types,
        sorted(set(hint_keys_sample))[:24],
        extra_norm,
        extra_vp,
    )


@dataclass
class NormalizationReadinessResult:
    """Draft vs auto-publish readiness after clause mapping (no DB reads)."""

    draft_blocked: bool
    draft_block_details: List[PolicyNormalizationFieldIssue] = field(default_factory=list)
    publishable: bool = False
    readiness_status: str = "not_publishable"
    readiness_issues: List[PolicyNormalizationFieldIssue] = field(default_factory=list)


def evaluate_normalization_readiness(
    policy_document: Dict[str, Any],
    normalized: Dict[str, Any],
    *,
    strict_require_conditions: bool = False,
    request_id: Optional[str] = None,
    document_id: Optional[str] = None,
) -> NormalizationReadinessResult:
    """
    Decide whether normalization may persist a meaningful draft (422 if draft_blocked) and whether
    that draft satisfies the same structural bar as policy_publish_gate for auto-publish.

    Draft is blocked when extraction is failed or when Layer 2 is empty and we have no usable scope
    to anchor a policy version narrative (unknown scope + no benefits/exclusions).
    Empty Layer 2 with a known scope (e.g. policy_summary + long-term) yields a persisted draft with
    publishable=False — not a normalization failure.
    """
    benefits = normalized.get("benefit_rules") or []
    exclusions = normalized.get("exclusions") or []
    conditions = normalized.get("conditions") or []

    det_type = (policy_document.get("detected_document_type") or "").strip()
    det_scope = (policy_document.get("detected_policy_scope") or "").strip()
    em = (
        policy_document.get("extracted_metadata")
        if isinstance(policy_document.get("extracted_metadata"), dict)
        else {}
    )
    meta_scope = str(em.get("policy_scope") or em.get("detected_policy_scope") or "").strip()

    has_scope = bool(det_scope and det_scope.lower() != "unknown") or bool(
        meta_scope and meta_scope.lower() != "unknown"
    )
    empty_layer2 = len(benefits) == 0 and len(exclusions) == 0
    processing_failed = (policy_document.get("processing_status") or "").lower() == "failed"

    draft_block_details: List[PolicyNormalizationFieldIssue] = []
    if processing_failed:
        draft_block_details.append(
            PolicyNormalizationFieldIssue(
                field="document.processing_status",
                issue="Source document is in a failed processing state; normalization cannot produce a reliable draft. "
                "Fix extraction or reprocess before normalizing.",
                expected="not failed",
                actual="failed",
            )
        )
    if empty_layer2 and not has_scope:
        draft_block_details.append(
            PolicyNormalizationFieldIssue(
                field="document.detected_policy_scope",
                issue="No assignment/policy scope detected and clause mapping produced no benefits or exclusions. "
                "Reprocess or upload a clearer policy.",
                expected="non-unknown scope or mappable Layer-2 rows",
                actual=det_scope or meta_scope or "unknown",
            )
        )
        draft_block_details.append(
            PolicyNormalizationFieldIssue(
                field="policy_versions[0].layer2_structure",
                issue="Cannot build a meaningful draft: no benefit rules or exclusions and scope is unknown.",
                expected="benefit_rules or exclusions non-empty, or known policy scope",
                actual="both empty",
            )
        )

    draft_blocked = len(draft_block_details) > 0

    readiness_issues: List[PolicyNormalizationFieldIssue] = []
    if not has_scope and not empty_layer2:
        log.info(
            "request_id=%s policy_norm stage=readiness_eval document_id=%s note=scope_unknown_layer2_ok",
            request_id,
            document_id,
        )

    publishable = not draft_blocked and not empty_layer2
    if not draft_blocked and empty_layer2:
        readiness_issues.append(
            PolicyNormalizationFieldIssue(
                field="policy_versions[0].layer2_structure",
                issue="No benefit rules or exclusions were mapped; a draft version will be created but it is not "
                "eligible for auto-publish until structured rows exist (aligns with employee publish gate).",
                expected="benefit_rules or exclusions non-empty for publish",
                actual="both empty",
            )
        )
        if det_type == DOC_TYPE_POLICY_SUMMARY:
            readiness_issues.append(
                PolicyNormalizationFieldIssue(
                    field="document.detected_document_type",
                    issue="Document is classified as policy_summary and produced no mappable benefit or exclusion clauses. "
                    "Upload the full policy PDF or reprocess with improved extraction to enable publish.",
                    expected="structured benefits/exclusions",
                    actual="policy_summary",
                )
            )

    if (
        not draft_blocked
        and strict_require_conditions
        and len(benefits) > 0
        and len(conditions) == 0
    ):
        publishable = False
        readiness_issues.append(
            PolicyNormalizationFieldIssue(
                field="policy_versions[0].conditions",
                issue="Strict mode: at least one condition row is required when benefit rules exist before auto-publish.",
                expected="len(conditions) > 0",
                actual="0",
            )
        )

    if draft_blocked:
        readiness_status = "normalization_blocked"
        publishable = False
    elif publishable:
        readiness_status = "publishable"
    elif strict_require_conditions and len(benefits) > 0 and len(conditions) == 0:
        readiness_status = "conditions_required_for_publish"
    elif empty_layer2:
        readiness_status = "draft_no_benefits_or_exclusions"
    else:
        readiness_status = "not_publishable"

    log.info(
        "request_id=%s policy_norm stage=readiness_eval document_id=%s draft_blocked=%s publishable=%s "
        "readiness_status=%s draft_block_count=%s readiness_issue_count=%s",
        request_id,
        document_id,
        draft_blocked,
        publishable,
        readiness_status,
        len(draft_block_details),
        len(readiness_issues),
    )

    return NormalizationReadinessResult(
        draft_blocked=draft_blocked,
        draft_block_details=draft_block_details,
        publishable=publishable,
        readiness_status=readiness_status,
        readiness_issues=readiness_issues,
    )


def readiness_for_auto_publish(
    policy_document: Dict[str, Any],
    normalized: Dict[str, Any],
    *,
    strict_require_conditions: bool = False,
    request_id: Optional[str] = None,
    document_id: Optional[str] = None,
) -> Tuple[bool, List[PolicyNormalizationFieldIssue]]:
    """
    Backward-compatible helper: returns (can_auto_publish, issues).

    If draft_blocked, issues are draft_block_details (normalization cannot proceed).
    If not publishable but draft is allowed, issues explain why auto-publish would be skipped.
    """
    r = evaluate_normalization_readiness(
        policy_document,
        normalized,
        strict_require_conditions=strict_require_conditions,
        request_id=request_id,
        document_id=document_id,
    )
    if r.draft_blocked:
        return False, list(r.draft_block_details)
    if not r.publishable:
        return False, list(r.readiness_issues)
    return True, []


def build_version_payload_for_validation(
    *,
    version_id: str,
    policy_id: str,
    doc_id: Optional[str],
    version_number: int,
    status: str,
    auto_generated: bool,
    review_status: str,
    confidence: Optional[float],
) -> Dict[str, Any]:
    return {
        "id": str(version_id),
        "policy_id": str(policy_id),
        "source_policy_document_id": str(doc_id) if doc_id else None,
        "version_number": int(version_number),
        "status": status,
        "auto_generated": bool(auto_generated),
        "review_status": review_status,
        "confidence": confidence,
    }


def json_preview_for_diagnostics(obj: Any, max_len: int = 8000) -> str:
    try:
        s = json.dumps(obj, default=str, indent=2)
        return s if len(s) <= max_len else s[:max_len] + "\n... truncated ..."
    except Exception as e:
        return f"<not serializable: {e}>"
