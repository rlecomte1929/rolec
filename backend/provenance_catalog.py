"""
Structured provenance for readiness + assignment-level compliance (trust, not legal advice).

URLs and titles live in seed JSON (repo-controlled). The UI must not hardcode immigration URLs;
it renders whatever the API returns from this catalog.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

REFERENCE_SET_VERSION = "2026-03-24.1"
CHECK_CATALOG_VERSION = "2026-03-24.1"
ASSIGNMENT_COMPLIANCE_ENGINE_VERSION = "assignment_compliance_engine_v1"

_DISCLAIMER_PRELIMINARY = (
    "Preliminary operational screening only — not a legal or immigration determination. "
    "A qualified professional must confirm eligibility and requirements."
)

_SEED_DIR = os.path.join(os.path.dirname(__file__), "seed_data")


def _load_json(name: str) -> Any:
    path = os.path.join(_SEED_DIR, name)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_references_for_route(destination_key: Optional[str], route_key: Optional[str]) -> List[Dict[str, Any]]:
    """Official / internal reference rows applicable to a destination+route (compact for API)."""
    payload = _load_json("compliance_reference_sources.json") or {}
    rows = payload.get("sources") or []
    dk = (destination_key or "").strip().upper() or None
    rk = (route_key or "employment").strip() or "employment"
    out: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        d = (r.get("destination_key") or "").strip().upper() or None
        rt = (r.get("route_key") or "").strip() or None
        if d and dk and d != dk:
            continue
        if rt and rt != rk:
            continue
        out.append(
            {
                "source_key": r.get("source_key"),
                "source_type": r.get("source_type"),
                "reference_strength": r.get("reference_strength"),
                "source_title": r.get("source_title"),
                "source_publisher": r.get("source_publisher"),
                "source_url": r.get("source_url"),
                "topic": r.get("topic"),
                "source_last_reviewed_at": r.get("source_last_reviewed_at"),
                "source_effective_date": r.get("source_effective_date"),
            }
        )
    return out


def checklist_source_map(destination_key: str, route_key: str) -> Dict[str, str]:
    """Maps checklist stable_key -> source_key."""
    payload = _load_json("readiness_checklist_provenance_map.json") or {}
    key = f"{destination_key.strip().upper()}:{(route_key or 'employment').strip()}"
    m = payload.get("maps") or {}
    raw = m.get(key) or {}
    return {str(k): str(v) for k, v in raw.items() if k and v}


def source_by_key(source_key: str) -> Optional[Dict[str, Any]]:
    payload = _load_json("compliance_reference_sources.json") or {}
    for r in payload.get("sources") or []:
        if isinstance(r, dict) and r.get("source_key") == source_key:
            return {
                "source_key": r.get("source_key"),
                "source_type": r.get("source_type"),
                "reference_strength": r.get("reference_strength"),
                "source_title": r.get("source_title"),
                "source_publisher": r.get("source_publisher"),
                "source_url": r.get("source_url"),
                "topic": r.get("topic"),
                "source_last_reviewed_at": r.get("source_last_reviewed_at"),
                "source_effective_date": r.get("source_effective_date"),
            }
    return None


def enrich_checklist_row(
    row: Dict[str, Any],
    destination_key: str,
    route_key: str,
) -> Dict[str, Any]:
    """Attach provenance + content tier to one checklist row (HR detail API)."""
    sk = (row.get("stable_key") or "").strip()
    cmap = checklist_source_map(destination_key, route_key)
    src_key = cmap.get(sk)
    src = source_by_key(src_key) if src_key else None
    tier = "internal_operational_guidance"
    human_review = True
    if src:
        st = (src.get("source_type") or "").lower()
        rs = (src.get("reference_strength") or "").lower()
        if st in ("official_gov", "official_agency") and rs == "official":
            tier = "official_source_pointer"
            human_review = True  # still not automated legal determination
        elif st in ("official_gov", "official_agency"):
            tier = "official_source_pointer"
        elif st == "company_policy":
            tier = "company_policy"
        else:
            tier = "internal_operational_guidance"
    out = dict(row)
    out["content_tier"] = tier
    out["human_review_required"] = human_review
    out["check_type"] = "advisory"
    out["primary_reference"] = src
    out["reference_note"] = (
        "Checklist item is operational guidance aligned to cited sources where mapped; "
        "it is not an automated verification of immigration eligibility."
        if src
        else "No mapped official reference for this item — treat as internal operational guidance; human review required."
    )
    return out


def readiness_summary_provenance_block(
    destination_key: str,
    route_key: str,
    template_resolved: bool,
) -> Dict[str, Any]:
    refs = list_references_for_route(destination_key, route_key)
    return {
        "reference_set_version": REFERENCE_SET_VERSION,
        "check_catalog_version": CHECK_CATALOG_VERSION,
        "disclaimer_legal": _DISCLAIMER_PRELIMINARY,
        "route_references": refs,
        "human_review_required": True,
        "trust_summary": (
            "Template checklist and milestones are internal operational guidance unless a row is linked to an "
            "official source below. Nothing here verifies legal eligibility."
            if template_resolved
            else "Readiness template data is not loaded; use official sources and qualified counsel."
        ),
    }


def degraded_readiness_payload(
    reason: str,
    destination_raw: Optional[str],
    destination_key: Optional[str],
    route_key: str,
) -> Dict[str, Any]:
    refs = list_references_for_route(destination_key, route_key) if destination_key else []
    msg = {
        "readiness_store_unavailable": (
            "The readiness reference database is not available on this environment "
            "(expected table `readiness_templates`). Apply migration "
            "`20260321000000_case_readiness_core.sql` or contact operations. "
            "Use official government sources and qualified immigration counsel for decisions."
        ),
        "no_template": (
            f"No verified readiness template is configured for destination {destination_key!r} "
            f"and route {route_key!r}. Human review required."
        ),
        "no_destination": "Destination could not be resolved from the employee profile or case; set host country / move plan.",
    }.get(
        reason,
        "Readiness could not be resolved; human review required.",
    )
    return {
        "user_message": msg,
        "human_review_required": True,
        "trust_tier": "unverified",
        "reference_set_version": REFERENCE_SET_VERSION,
        "check_catalog_version": CHECK_CATALOG_VERSION,
        "disclaimer_legal": _DISCLAIMER_PRELIMINARY,
        "route_references": refs,
        "route_references_note": (
            "Pointers to authoritative sites for HR diligence — not verified claims about this assignee."
            if refs
            else None
        ),
    }


def build_assignment_compliance_explanation(
    assignment_id: str,
    profile_present: bool,
    report: Dict[str, Any],
) -> Dict[str, Any]:
    """Step-by-step narrative for assignment-level compliance_engine runs."""
    checks = report.get("checks") or []
    actions = report.get("actions") or []
    steps: List[Dict[str, Any]] = [
        {
            "step": 1,
            "title": "Context resolved",
            "detail": {
                "assignment_id": assignment_id,
                "employee_profile_present": profile_present,
            },
        },
        {
            "step": 2,
            "title": "Checks executed",
            "detail": {
                "count": len(checks),
                "items": [
                    {
                        "id": c.get("id"),
                        "name": c.get("name"),
                        "status": c.get("status"),
                        "output_category": c.get("output_category"),
                        "human_review_required": c.get("human_review_required"),
                    }
                    for c in checks
                ],
            },
        },
        {
            "step": 3,
            "title": "Generated actions",
            "detail": {"count": len(actions), "items": [{"title": a} if isinstance(a, str) else a for a in actions]},
        },
        {
            "step": 4,
            "title": "Overall outcome",
            "detail": {
                "overallStatus": report.get("overallStatus"),
                "verdict_explanation": report.get("verdict_explanation"),
            },
        },
    ]
    return {"steps": steps}


def enrich_assignment_compliance_report(
    report: Dict[str, Any],
    *,
    assignment_id: str,
    profile_present: bool,
) -> Dict[str, Any]:
    """Add provenance, categories, and explanation — mutates and returns report."""
    rules_meta = _load_json("mobility_rules_provenance.json") or {}
    pack = rules_meta.get("rule_pack") or {}
    out = dict(report)
    checks_out: List[Dict[str, Any]] = []
    for c in out.get("checks") or []:
        if not isinstance(c, dict):
            continue
        enriched = dict(c)
        enriched["output_category"] = "internal_operational_rule"
        enriched["check_type"] = "deterministic"
        enriched["reference_strength"] = "internal"
        enriched["human_review_required"] = c.get("status") in ("NEEDS_REVIEW", "NON_COMPLIANT")
        enriched["primary_reference"] = {
            "source_type": pack.get("source_type", "company_policy"),
            "source_title": pack.get("source_title", "ReloPass mobility rule pack"),
            "reference_strength": pack.get("reference_strength", "internal"),
            "source_last_reviewed_at": pack.get("source_last_reviewed_at"),
        }
        enriched["rationale_legal_safety"] = (
            "Derived from configured internal policy rules (mobility_rules.json / defaults), "
            "not from immigration law."
        )
        checks_out.append(enriched)
    out["checks"] = checks_out
    actions_typed: List[Dict[str, Any]] = []
    for a in out.get("actions") or []:
        if isinstance(a, str):
            actions_typed.append(
                {
                    "title": a,
                    "output_category": "internal_operational_guidance",
                    "human_review_required": True,
                }
            )
        else:
            actions_typed.append(a)
    out["actions"] = actions_typed
    overall = out.get("overallStatus")
    if overall == "COMPLIANT":
        verdict = "attention_needed_low"
        expl = "Internal policy checks passed; immigration eligibility was not evaluated."
    elif overall == "NON_COMPLIANT":
        verdict = "attention_needed"
        expl = "Internal policy checks found gaps; immigration eligibility was not evaluated."
    else:
        verdict = "cannot_verify_internal_rules"
        expl = "Incomplete data or review items under internal policy; immigration eligibility was not evaluated."
    out["verdict_explanation"] = expl
    out["outcome_verdict"] = verdict
    out["meta"] = {
        "engine_version": ASSIGNMENT_COMPLIANCE_ENGINE_VERSION,
        "reference_set_version": REFERENCE_SET_VERSION,
        "rule_pack_title": pack.get("source_title"),
        "preliminary_only": True,
        "not_legal_determination": True,
    }
    out["explanation"] = build_assignment_compliance_explanation(assignment_id, profile_present, out)
    out["disclaimer_legal"] = _DISCLAIMER_PRELIMINARY
    return out
