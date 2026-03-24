"""
Grouped policy item comparison readiness — avoids forcing narrative rows into budget comparison.

Emits coverage_status, value_type, comparison_readiness, and reason for HR review,
employee-facing context, and future comparison-engine inputs.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# comparison_readiness (API-stable)
READINESS_COMPARISON_READY = "comparison_ready"
READINESS_INFORMATIONAL_ONLY = "informational_only"
READINESS_EXTERNAL_REFERENCE_PARTIAL = "external_reference_partial"
READINESS_REVIEW_REQUIRED = "review_required"
READINESS_DETERMINISTIC_NON_BUDGET = "deterministic_non_budget"

_VAGUE_RE = re.compile(
    r"\b(?:may|might|could|subject to|depending on|at (?:the )?discretion|where appropriate|"
    r"as appropriate|case[- ]by[- ]case|if approved|when approved|as needed|described elsewhere)\b",
    re.I,
)
_CURRENCY_RE = re.compile(r"\b(USD|EUR|GBP|CHF|CAD|AUD|SGD|NZD)\b", re.I)


def _currency_from_drafts(group_drafts: List[Dict[str, Any]]) -> Optional[str]:
    for d in group_drafts:
        af = d.get("amount_fragments") if isinstance(d.get("amount_fragments"), dict) else {}
        c = af.get("currency")
        if isinstance(c, str) and c.strip():
            return c.strip().upper()[:8]
    return None


def _currency_from_text(text: str) -> Optional[str]:
    m = _CURRENCY_RE.search(text or "")
    return m.group(1).upper() if m else None


def _parseable_amount_tiers(gv: Dict[str, Any]) -> bool:
    tiers = gv.get("amount_tiers") or []
    if not isinstance(tiers, list) or not tiers:
        return False
    for t in tiers:
        if not isinstance(t, dict):
            continue
        raw = t.get("amount_text")
        if raw is None:
            continue
        try:
            v = float(str(raw).replace(",", ""))
            if v > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _duration_signal(gv: Dict[str, Any]) -> bool:
    d = gv.get("duration_days")
    return isinstance(d, int) and d > 0


def _externally_governed(gv: Dict[str, Any]) -> bool:
    eg = gv.get("external_governance")
    return isinstance(eg, dict) and bool(eg.get("is_externally_governed"))


def classify_grouped_item_readiness(
    item: Dict[str, Any],
    group_drafts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Classify one grouped policy item for comparison UX.

    Returns keys: coverage_status, value_type, comparison_readiness, reason
    """
    gv = item.get("grouped_values") if isinstance(item.get("grouped_values"), dict) else {}
    ck = item.get("canonical_key")
    hint = str(item.get("comparison_readiness_hint") or "partial")
    base_cov = str(item.get("coverage_status") or "mentioned")
    summary = item.get("summary") or ""
    summary_l = summary.lower()
    draft_unresolved = bool(item.get("draft_only_unresolved"))
    explicit_cap = bool(item.get("explicit_numeric_cap"))

    if draft_unresolved or not ck:
        return {
            "coverage_status": "ambiguous",
            "value_type": "unknown",
            "comparison_readiness": READINESS_REVIEW_REQUIRED,
            "reason": "No canonical topic match or draft-only unresolved row; HR clarification needed.",
        }

    exclusion = any(bool(d.get("candidate_exclusion_flag")) for d in group_drafts if isinstance(d, dict))
    if exclusion or base_cov == "excluded":
        return {
            "coverage_status": "excluded" if exclusion or base_cov == "excluded" else base_cov,
            "value_type": "exclusion",
            "comparison_readiness": READINESS_DETERMINISTIC_NON_BUDGET,
            "reason": "Exclusion or negative coverage is deterministic for eligibility, not a budget delta.",
        }

    currency = _currency_from_drafts(group_drafts) or _currency_from_text(summary)
    tiers_ok = _parseable_amount_tiers(gv)
    dur_ok = _duration_signal(gv)
    ext_gov = _externally_governed(gv)

    # Informational compensation / policy narrative rows
    if ck == "policy_definitions_and_exceptions" or gv.get("informational_compensation_topics"):
        return {
            "coverage_status": base_cov if base_cov != "ambiguous" else "mentioned",
            "value_type": "narrative",
            "comparison_readiness": READINESS_INFORMATIONAL_ONLY,
            "reason": "Compensation or policy framing row; not modeled as an employee budget comparison benefit.",
        }

    # Strong budget signals
    if (explicit_cap or tiers_ok) and currency:
        return {
            "coverage_status": "specified" if base_cov == "mentioned" else base_cov,
            "value_type": "amount",
            "comparison_readiness": READINESS_COMPARISON_READY,
            "reason": "Explicit monetary value with currency supports cap or allowance comparison.",
        }
    if tiers_ok and not currency:
        return {
            "coverage_status": "specified",
            "value_type": "amount",
            "comparison_readiness": READINESS_REVIEW_REQUIRED,
            "reason": "Amount tiers detected but currency not confirmed; confirm currency for comparison.",
        }

    if dur_ok:
        return {
            "coverage_status": "specified" if base_cov == "mentioned" else base_cov,
            "value_type": "duration",
            "comparison_readiness": READINESS_COMPARISON_READY,
            "reason": "Explicit duration (e.g. days cap) supports duration-based comparison.",
        }

    # Visa / permits: narrative coverage without budget figures; do not upgrade to external-partial from hints alone.
    if ck == "work_permits_and_visas":
        return {
            "coverage_status": "covered" if base_cov == "mentioned" else base_cov,
            "value_type": "narrative",
            "comparison_readiness": READINESS_INFORMATIONAL_ONLY,
            "reason": "Visa and permit support described without numeric cap; informational coverage compare only.",
        }

    # Host housing external cap before generic external governance (preserves capped_external status).
    if ck == "host_housing" and (
        gv.get("cap_basis") == "external_or_third_party"
        or hint == "external_reference"
    ):
        return {
            "coverage_status": "capped_external",
            "value_type": "external_reference",
            "comparison_readiness": READINESS_EXTERNAL_REFERENCE_PARTIAL,
            "reason": "Host housing cap tied to external or third-party data unless an explicit amount is captured.",
        }

    if ck == "home_leave":
        if ext_gov or "as per" in summary_l or "global travel" in summary_l:
            return {
                "coverage_status": "covered",
                "value_type": "narrative",
                "comparison_readiness": READINESS_EXTERNAL_REFERENCE_PARTIAL,
                "reason": "Leave entitlements may reference external travel policy; not a single budget figure.",
            }
        if gv.get("leave_variants"):
            return {
                "coverage_status": "specified",
                "value_type": "narrative",
                "comparison_readiness": READINESS_INFORMATIONAL_ONLY,
                "reason": "Leave variants are narrative structure without guaranteed numeric comparison.",
            }

    # External policy / third-party benchmark dependency (non-home-leave / non-visa rows)
    if ext_gov or hint in ("external_reference", "not_ready"):
        if explicit_cap and currency:
            return {
                "coverage_status": base_cov,
                "value_type": "mixed",
                "comparison_readiness": READINESS_EXTERNAL_REFERENCE_PARTIAL,
                "reason": "Numeric hints present but wording references external policy or third-party data; treat comparison as partial.",
            }
        return {
            "coverage_status": base_cov if base_cov != "mentioned" else "covered",
            "value_type": "external_reference",
            "comparison_readiness": READINESS_EXTERNAL_REFERENCE_PARTIAL,
            "reason": "Depends on another policy, vendor data, or benchmark; not a closed numeric comparison.",
        }

    if _VAGUE_RE.search(summary_l) and not (tiers_ok or dur_ok or explicit_cap):
        return {
            "coverage_status": "conditional",
            "value_type": "narrative",
            "comparison_readiness": READINESS_REVIEW_REQUIRED,
            "reason": "Predominantly discretionary or vague wording; HR should confirm before comparison use.",
        }

    # Default: narrative coverage without structured cap
    return {
        "coverage_status": base_cov,
        "value_type": "narrative",
        "comparison_readiness": READINESS_INFORMATIONAL_ONLY,
        "reason": "Coverage described without explicit comparable cap or duration.",
    }


def enrich_grouped_items_with_readiness(
    grouped_items: List[Dict[str, Any]],
    cluster_drafts_by_group_id: Dict[str, List[Dict[str, Any]]],
) -> None:
    """Mutate each grouped item with ``readiness`` and align legacy coverage when helpful."""
    for g in grouped_items:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("grouped_item_id") or "")
        drafts = cluster_drafts_by_group_id.get(gid, [])
        readiness = classify_grouped_item_readiness(g, drafts)
        g["readiness"] = readiness
        # Keep top-level coverage_status in sync for consumers that read it first
        if readiness.get("coverage_status"):
            g["coverage_status"] = readiness["coverage_status"]


def build_comparison_engine_grouped_readiness_payload(
    grouped_items: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Compact list for comparison workers (canonical id + readiness + key)."""
    out: List[Dict[str, Any]] = []
    for g in grouped_items:
        if not isinstance(g, dict):
            continue
        r = g.get("readiness") if isinstance(g.get("readiness"), dict) else {}
        out.append(
            {
                "grouped_item_id": g.get("grouped_item_id"),
                "canonical_key": g.get("canonical_key"),
                "taxonomy_service_key": g.get("taxonomy_service_key"),
                "readiness": r,
            }
        )
    return out
