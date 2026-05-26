"""
Employee-facing entitlement read model: truthful policy maturity + per-service rows.

Read-only: never invent caps; comparison state is explicit when the engine is not ready.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .policy_comparison_readiness import evaluate_version_comparison_readiness
from .policy_entitlement_model import (
    CANONICAL_SERVICE_TO_CATEGORY,
    canonical_service_for_legacy_benefit_key,
)
from .policy_processing_readiness import evaluate_stored_policy_readiness
from .policy_resolution import (
    collect_company_id_candidates_for_assignment,
    resolve_benefits_matrix_for_version,
)

log = logging.getLogger(__name__)

PolicyStatus = str

TOP_LEVEL_EXPLANATIONS: Dict[str, str] = {
    "no_policy": "Your employer has not linked a relocation policy to this assignment yet.",
    "draft_only": "HR is still preparing policy details; only summary-level information is available.",
    "normalized_not_publishable": "HR has drafted benefit rules that are not published yet; values below are informational until publish.",
    "published_not_comparison_ready": "Your published policy is available below. Cost comparison across services is not fully enabled yet.",
    "published_comparison_ready": "Your published policy is available; service limits are structured for comparison where applicable.",
}


def _derive_policy_source(policy_row: Dict[str, Any]) -> str:
    src = (policy_row.get("template_source") or "company_uploaded") or "company_uploaded"
    if src == "default_platform_template":
        return "starter_template"
    if src in ("company_uploaded", "import", "manual"):
        return str(src)
    return str(src)


def find_first_company_policy_bundle(
    db: Any, company_ids: List[str]
) -> Optional[Tuple[str, Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]]:
    """
    First candidate company with a company_policies row.
    Returns (company_id, policy, latest_version, published_version_or_none).
    """
    for cid in company_ids:
        try:
            policies = db.list_company_policies(cid)
        except Exception as exc:
            log.warning("entitlements list_company_policies failed company_id=%s exc=%s", cid, exc)
            continue
        if not policies:
            continue
        policy = policies[0]
        pid = policy.get("id")
        if not pid:
            continue
        try:
            versions = db.list_policy_versions(str(pid))
        except Exception as exc:
            log.warning("entitlements list_policy_versions failed policy_id=%s exc=%s", pid, exc)
            versions = []
        latest = versions[0] if versions else None
        try:
            published = db.get_published_policy_version(str(pid))
        except Exception as exc:
            log.warning("entitlements get_published_policy_version failed policy_id=%s exc=%s", pid, exc)
            published = None
        return str(cid), policy, latest, published
    return None


def classify_employee_policy_status(
    db: Any,
    *,
    published_ver: Optional[Dict[str, Any]],
    latest_ver: Optional[Dict[str, Any]],
) -> PolicyStatus:
    if published_ver and published_ver.get("id"):
        cr = evaluate_version_comparison_readiness(db, str(published_ver["id"]))
        if cr.get("comparison_ready"):
            return "published_comparison_ready"
        return "published_not_comparison_ready"
    if not latest_ver or not latest_ver.get("id"):
        return "draft_only"
    vid = str(latest_ver["id"])
    try:
        br = db.list_policy_benefit_rules(vid)
        ex = db.list_policy_exclusions(vid)
    except Exception as exc:
        log.warning("entitlements classify layer2 load failed version_id=%s exc=%s", vid, exc)
        br, ex = [], []
    if (not br or len(br) == 0) and (not ex or len(ex) == 0):
        return "draft_only"
    return "normalized_not_publishable"


def _score_benefit_row(b: Dict[str, Any]) -> Tuple[int, float]:
    if not b.get("included"):
        return (0, 0.0)
    for k in ("max_value", "standard_value", "min_value"):
        v = b.get(k)
        if v is not None:
            try:
                return (1, float(v))
            except (TypeError, ValueError):
                return (1, 0.0)
    return (1, 0.0)


def _pick_primary_benefit(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return max(rows, key=_score_benefit_row)


def _coverage_status_from_benefit(b: Dict[str, Any]) -> str:
    if not b.get("included"):
        return "excluded"
    if b.get("max_value") is not None or b.get("standard_value") is not None or b.get("min_value") is not None:
        return "included"
    return "conditional"


def _effective_limit_from_benefit(b: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Only values present on the resolved rule — never synthesized caps."""
    if b.get("max_value") is not None:
        return {
            "kind": "max",
            "value": b.get("max_value"),
            "currency": b.get("currency"),
            "unit": b.get("amount_unit"),
        }
    if b.get("standard_value") is not None:
        return {
            "kind": "standard",
            "value": b.get("standard_value"),
            "currency": b.get("currency"),
            "unit": b.get("amount_unit"),
        }
    if b.get("min_value") is not None:
        return {
            "kind": "min",
            "value": b.get("min_value"),
            "currency": b.get("currency"),
            "unit": b.get("amount_unit"),
        }
    return None


def _employee_visible_value(b: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"read_only": True}
    if b.get("included") is not None:
        out["included"] = bool(b.get("included"))
    for k in ("standard_value", "max_value", "min_value", "currency", "amount_unit", "frequency"):
        if b.get(k) is not None:
            out[k] = b.get(k)
    cs = b.get("condition_summary")
    if cs:
        out["condition_summary"] = cs
    return out


def _build_entitlement_rows(
    benefits: List[Dict[str, Any]],
    *,
    policy_published: bool,
    comparison_ready: bool,
    comparison_explanation_global: str,
) -> List[Dict[str, Any]]:
    from collections import defaultdict

    by_service: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for b in benefits:
        bk = (b.get("benefit_key") or "").strip()
        sk = canonical_service_for_legacy_benefit_key(bk) or bk
        by_service[str(sk)].append(b)

    rows: List[Dict[str, Any]] = []
    for service_key in sorted(by_service.keys()):
        group = by_service[service_key]
        primary = _pick_primary_benefit(group)
        cat = CANONICAL_SERVICE_TO_CATEGORY.get(service_key)
        category = cat.value if cat else "misc"

        notes: List[str] = []
        if len(group) > 1:
            notes.append("Multiple policy rules map to this service; the primary row is shown.")

        if not policy_published:
            svc_cmp_explanation = (
                "Comparison is evaluated only after HR publishes the policy; values below are informational."
            )
            svc_cmp_ready = False
        elif not comparison_ready:
            svc_cmp_explanation = (
                comparison_explanation_global
                or "Policy comparison is not fully ready; within/exceeds is not evaluated."
            )
            svc_cmp_ready = False
        else:
            svc_cmp_explanation = "This service participates in published policy comparison when limits apply."
            svc_cmp_ready = True

        rows.append(
            {
                "service_key": service_key,
                "category": category,
                "coverage_status": _coverage_status_from_benefit(primary),
                "effective_limit": _effective_limit_from_benefit(primary),
                "approval_required": bool(primary.get("approval_required")),
                "employee_visible_value": _employee_visible_value(primary),
                "notes": notes,
                "comparison_readiness": {
                    "comparison_ready": svc_cmp_ready,
                    "explanation": svc_cmp_explanation,
                },
                "explanation": (
                    "Draft or unpublished policy — informational only until HR publishes."
                    if not policy_published
                    else (
                        "Shown from your published employer policy."
                        if comparison_ready
                        else "Shown from your published policy; comparison engine is not fully ready for cap checks."
                    )
                ),
            }
        )
    return rows


def build_employee_entitlement_read_model(
    db: Any,
    assignment_id: str,
    assignment: Dict[str, Any],
    case: Optional[Dict[str, Any]],
    profile: Optional[Dict[str, Any]],
    employee_profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    candidates = collect_company_id_candidates_for_assignment(db, assignment, case)
    if not candidates:
        return {
            "policy_status": "no_policy",
            "policy_source": None,
            "publish_readiness": {"status": "not_ready", "issues": [{"code": "NO_COMPANY", "message": "No company context for policy."}]},
            "comparison_readiness": {
                "comparison_ready": False,
                "comparison_blockers": ["NO_PUBLISHED_POLICY"],
                "partial_numeric_coverage": False,
                "evaluated": False,
                "explanation": "No employer policy is linked; comparison does not apply.",
            },
            "explanation": TOP_LEVEL_EXPLANATIONS["no_policy"],
            "entitlements": [],
            "assignment_id": assignment_id,
            "company_id": None,
            "policy_id": None,
            "version_id": None,
        }

    bundle = find_first_company_policy_bundle(db, candidates)
    if not bundle:
        return {
            "policy_status": "no_policy",
            "policy_source": None,
            "publish_readiness": {"status": "not_ready", "issues": [{"code": "NO_POLICY", "message": "No company policy record."}]},
            "comparison_readiness": {
                "comparison_ready": False,
                "comparison_blockers": ["NO_PUBLISHED_POLICY"],
                "partial_numeric_coverage": False,
                "evaluated": False,
                "explanation": "No employer policy is linked; comparison does not apply.",
            },
            "explanation": TOP_LEVEL_EXPLANATIONS["no_policy"],
            "entitlements": [],
            "assignment_id": assignment_id,
            "company_id": None,
            "policy_id": None,
            "version_id": None,
        }

    company_id, policy_row, latest_ver, published_ver = bundle
    policy_status = classify_employee_policy_status(db, published_ver=published_ver, latest_ver=latest_ver)
    policy_source = _derive_policy_source(policy_row)

    version_for_matrix = published_ver if published_ver else latest_ver
    version_for_readiness = version_for_matrix
    benefits: List[Dict[str, Any]] = []

    if version_for_matrix and version_for_matrix.get("id"):
        vid = str(version_for_matrix["id"])
        try:
            benefit_rules = db.list_policy_benefit_rules(vid)
            exclusions = db.list_policy_exclusions(vid)
            conditions = db.list_policy_rule_conditions(vid)
            assignment_applicability = db.list_policy_assignment_applicability(vid)
        except Exception as exc:
            log.warning("entitlements readiness load failed version_id=%s exc=%s", vid, exc)
            benefit_rules, exclusions, conditions, assignment_applicability = [], [], [], []

        source_document = None
        doc_id = version_for_readiness.get("source_policy_document_id") if version_for_readiness else None
        if doc_id:
            try:
                source_document = db.get_policy_document(str(doc_id))
            except Exception:
                source_document = None

        try:
            readiness_env = evaluate_stored_policy_readiness(
                latest_version=version_for_readiness,
                published_version=published_ver,
                benefit_rules=benefit_rules,
                exclusions=exclusions,
                conditions=conditions,
                assignment_applicability=assignment_applicability,
                source_document=source_document,
            )
            publish_readiness = readiness_env.get("publish_readiness") or {"status": "unknown", "issues": []}
        except Exception as exc:
            log.warning("entitlements evaluate_stored_policy_readiness failed exc=%s", exc)
            publish_readiness = {"status": "not_ready", "issues": [{"code": "READINESS_ERROR", "message": str(exc)[:200]}]}

        persist = bool(published_ver)
        try:
            resolved = resolve_benefits_matrix_for_version(
                db,
                assignment_id,
                assignment,
                case,
                profile,
                employee_profile,
                company_id=company_id,
                policy_row=policy_row,
                version_row=version_for_matrix,
                persist_resolution=persist,
            )
        except Exception as exc:
            log.warning("entitlements resolve_benefits_matrix failed assignment_id=%s exc=%s", assignment_id, exc)
            resolved = None
        if resolved:
            benefits = list(resolved.get("benefits") or [])
    else:
        publish_readiness = {"status": "not_ready", "issues": [{"code": "NO_VERSION", "message": "No policy version exists."}]}

    if published_ver and published_ver.get("id"):
        comparison_readiness = evaluate_version_comparison_readiness(db, str(published_ver["id"]))
        comparison_readiness = dict(comparison_readiness)
        comparison_readiness["evaluated"] = True
        if comparison_readiness.get("comparison_ready"):
            comparison_readiness["explanation"] = (
                "Published policy meets structural checks for employee service comparison."
            )
        else:
            blockers = comparison_readiness.get("comparison_blockers") or []
            comparison_readiness["explanation"] = (
                "Published policy is not fully comparison-ready: " + ", ".join(str(b) for b in blockers[:5])
                + ("…" if len(blockers) > 5 else "")
            )
        comparison_ready = bool(comparison_readiness.get("comparison_ready"))
        comparison_explanation_global = str(comparison_readiness.get("explanation") or "")
    else:
        comparison_readiness = {
            "comparison_ready": False,
            "comparison_blockers": ["NO_PUBLISHED_POLICY"],
            "partial_numeric_coverage": False,
            "evaluated": False,
            "explanation": "No published policy version; comparison is not evaluated (not treated as within/exceeds).",
        }
        comparison_ready = False
        comparison_explanation_global = comparison_readiness["explanation"]

    entitlements = _build_entitlement_rows(
        benefits,
        policy_published=bool(published_ver),
        comparison_ready=comparison_ready,
        comparison_explanation_global=comparison_explanation_global,
    )

    return {
        "policy_status": policy_status,
        "policy_source": policy_source,
        "publish_readiness": publish_readiness,
        "comparison_readiness": comparison_readiness,
        "explanation": TOP_LEVEL_EXPLANATIONS.get(policy_status, TOP_LEVEL_EXPLANATIONS["no_policy"]),
        "entitlements": entitlements,
        "assignment_id": assignment_id,
        "company_id": company_id,
        "policy_id": policy_row.get("id"),
        "version_id": (published_ver or latest_ver or {}).get("id"),
    }
