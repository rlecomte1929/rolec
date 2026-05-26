"""
Per-rule and policy-level comparison readiness for ReloPass.

Distinguishes:
- **full** — numeric/duration caps, deterministic inclusion/exclusion, or other deterministic comparison
- **partial** — coverage/included/excluded/conditional can be shown; budget delta vs quotes not reliable
- **not_ready** — too ambiguous to use safely in automated comparison

Publishability (Layer 2) can be true while comparison remains partial or not_ready.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from .policy_comparison_readiness import (
    EMPLOYEE_COMPARISON_REQUIRED_BENEFIT_KEYS,
    _parse_metadata,
    benefit_rule_has_decision_signal,
)

RULE_COMPARISON_FULL = "full"
RULE_COMPARISON_PARTIAL = "partial"
RULE_COMPARISON_NOT_READY = "not_ready"

_VAGUE_COVERAGE_RE = re.compile(
    r"\b(?:may|might|could|can be|subject to|depending on|at (?:the )?discretion|where appropriate|as appropriate|"
    r"on a case[- ]by[- ]case basis|if approved|when approved|as needed|may be available|might be available)\b",
    re.I,
)

_DURATION_UNITS = frozenset(
    {
        "day",
        "days",
        "night",
        "nights",
        "week",
        "weeks",
        "month",
        "months",
        "working days",
        "working day",
    }
)


def _truthy(v: Any) -> bool:
    if v is True:
        return True
    if v is False or v is None:
        return False
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "y")
    return bool(v)


def _text_fuzzy_included(raw: str) -> bool:
    rl = (raw or "").lower()
    if not rl.strip():
        return False
    if "not covered" in rl or "does not cover" in rl or "excluded" in rl:
        return False
    return bool(
        re.search(
            r"\b(?:included|provided|eligible|available|covered|payable|reimbursed|allowance|benefit)\b",
            rl,
        )
    )


def _has_numeric_budget_signal(rule: Dict[str, Any]) -> bool:
    """Amount/percent/currency suitable for envelope vs cap comparison."""
    meta = _parse_metadata(rule)
    av = rule.get("amount_value")
    if av is not None:
        try:
            if float(av) > 0:
                if rule.get("currency") or meta.get("currency"):
                    return True
                ct = (rule.get("calc_type") or "").lower()
                if ct in ("percent_salary", "per_diem", "unit_cap", "flat_amount", "reimbursement", "difference_only"):
                    return True
                if "%" in (rule.get("raw_text") or "") or "percent" in (rule.get("raw_text") or "").lower():
                    return True
        except (TypeError, ValueError):
            pass
    for k in ("max_value", "standard_value", "min_value"):
        v = meta.get(k)
        if v is not None:
            try:
                if float(v) > 0:
                    return True
            except (TypeError, ValueError):
                pass
    ct = (rule.get("calc_type") or "").lower()
    if ct == "percent_salary" and av is not None:
        try:
            return float(av) > 0
        except (TypeError, ValueError):
            pass
    return False


def _has_duration_cap(rule: Dict[str, Any]) -> bool:
    unit = (rule.get("amount_unit") or "").strip().lower()
    if not unit:
        return False
    if unit not in _DURATION_UNITS and not any(u in unit for u in ("day", "night", "week", "month")):
        return False
    av = rule.get("amount_value")
    if av is None:
        return False
    try:
        return float(av) > 0
    except (TypeError, ValueError):
        return False


def evaluate_rule_comparison_readiness(
    rule: Dict[str, Any],
    *,
    rule_kind: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluate one rule for service/budget comparison surfaces.

    rule_kind: ``benefit_rule`` | ``exclusion`` | ``draft_candidate`` | None (auto-detect).

    Returns:
        level: full | partial | not_ready
        supports_budget_delta: bool — safe for numeric variance / delta vs quotes
        reasons: list of short machine codes for UI/diagnostics
    """
    reasons: List[str] = []

    kind = rule_kind
    if kind is None:
        if rule.get("candidate_coverage_status") is not None or rule.get("publishability_assessment") is not None:
            kind = "draft_candidate"
        elif rule.get("domain") is not None and rule.get("calc_type") is None:
            kind = "exclusion"
        else:
            kind = "benefit_rule"

    if kind == "exclusion":
        reasons.append("DETERMINISTIC_EXCLUSION")
        return {
            "level": RULE_COMPARISON_FULL,
            "supports_budget_delta": False,
            "reasons": reasons,
        }

    if kind == "draft_candidate":
        return _evaluate_draft_candidate_rule(rule)

    # benefit_rule (Layer-2 shape, may include internal _clause_* keys)
    meta = _parse_metadata(rule)
    raw = (rule.get("raw_text") or rule.get("description") or "")[:4000]
    conf = rule.get("confidence")
    try:
        conf_f = float(conf) if conf is not None else 0.75
    except (TypeError, ValueError):
        conf_f = 0.75

    if meta.get("allowed") is False:
        reasons.append("EXPLICIT_NOT_ALLOWED")
        return {
            "level": RULE_COMPARISON_FULL,
            "supports_budget_delta": False,
            "reasons": reasons,
        }

    if _has_duration_cap(rule):
        reasons.append("DURATION_UNIT_CAP")
        return {
            "level": RULE_COMPARISON_FULL,
            "supports_budget_delta": True,
            "reasons": reasons,
        }

    if _has_numeric_budget_signal(rule):
        reasons.append("NUMERIC_OR_PERCENT_CAP")
        return {
            "level": RULE_COMPARISON_FULL,
            "supports_budget_delta": True,
            "reasons": reasons,
        }

    vague = bool(_VAGUE_COVERAGE_RE.search(raw))
    if vague and not _has_numeric_budget_signal(rule) and not _has_duration_cap(rule):
        if conf_f < 0.55:
            reasons.append("VAGUE_LOW_CONFIDENCE")
            return {
                "level": RULE_COMPARISON_NOT_READY,
                "supports_budget_delta": False,
                "reasons": reasons,
            }
        reasons.append("VAGUE_FRAMING")
        return {
            "level": RULE_COMPARISON_PARTIAL,
            "supports_budget_delta": False,
            "reasons": reasons,
        }

    if benefit_rule_has_decision_signal(rule):
        if _truthy(meta.get("approval_required")):
            reasons.append("APPROVAL_GATE_WITHOUT_NUMERIC")
        else:
            reasons.append("DECISION_SIGNAL_NON_NUMERIC")
        return {
            "level": RULE_COMPARISON_PARTIAL,
            "supports_budget_delta": False,
            "reasons": reasons,
        }

    bk = (rule.get("benefit_key") or "").strip()
    if bk and _text_fuzzy_included(raw):
        reasons.append("COVERAGE_LANGUAGE_ONLY")
        return {
            "level": RULE_COMPARISON_PARTIAL,
            "supports_budget_delta": False,
            "reasons": reasons,
        }

    if bk:
        reasons.append("BENEFIT_KEY_WITHOUT_COMPARISON_SIGNAL")
        return {
            "level": RULE_COMPARISON_PARTIAL,
            "supports_budget_delta": False,
            "reasons": reasons,
        }

    reasons.append("AMBIGUOUS_OR_UNMAPPED")
    return {
        "level": RULE_COMPARISON_NOT_READY,
        "supports_budget_delta": False,
        "reasons": reasons,
    }


def _evaluate_draft_candidate_rule(rule: Dict[str, Any]) -> Dict[str, Any]:
    reasons: List[str] = []
    excerpt = (rule.get("source_excerpt") or "")[:4000]
    try:
        conf_f = float(rule.get("confidence") or 0.75)
    except (TypeError, ValueError):
        conf_f = 0.75

    if rule.get("candidate_exclusion_flag"):
        reasons.append("DRAFT_EXCLUSION_INTENT")
        return {
            "level": RULE_COMPARISON_FULL,
            "supports_budget_delta": False,
            "reasons": reasons,
        }

    af = rule.get("amount_fragments") or {}
    nums = af.get("numeric_values_hint") or []
    if isinstance(nums, list) and nums and (af.get("currency") or excerpt.upper().find("EUR") >= 0 or "USD" in excerpt.upper()):
        try:
            if float(nums[0]) > 0:
                reasons.append("DRAFT_NUMERIC_FRAGMENT")
                return {
                    "level": RULE_COMPARISON_FULL,
                    "supports_budget_delta": True,
                    "reasons": reasons,
                }
        except (TypeError, ValueError, IndexError):
            pass

    dur = rule.get("duration_quantity_fragments") or {}
    if isinstance(dur, dict) and dur.get("quantity") and dur.get("unit"):
        reasons.append("DRAFT_DURATION_FRAGMENT")
        return {
            "level": RULE_COMPARISON_FULL,
            "supports_budget_delta": True,
            "reasons": reasons,
        }

    cov = (rule.get("candidate_coverage_status") or "").lower()
    vague = bool(_VAGUE_COVERAGE_RE.search(excerpt))
    if vague:
        if conf_f < 0.55:
            reasons.append("VAGUE_LOW_CONFIDENCE")
            return {
                "level": RULE_COMPARISON_NOT_READY,
                "supports_budget_delta": False,
                "reasons": reasons,
            }
        reasons.append("VAGUE_FRAMING")
        return {
            "level": RULE_COMPARISON_PARTIAL,
            "supports_budget_delta": False,
            "reasons": reasons,
        }

    if cov in ("conditional", "mentioned"):
        reasons.append("DRAFT_CONDITIONAL_OR_MENTION")
        return {
            "level": RULE_COMPARISON_PARTIAL,
            "supports_budget_delta": False,
            "reasons": reasons,
        }

    if cov == "capped":
        reasons.append("DRAFT_MARKED_CAPPED_WITHOUT_PARSE")
        return {
            "level": RULE_COMPARISON_PARTIAL,
            "supports_budget_delta": False,
            "reasons": reasons,
        }

    reasons.append("DRAFT_INSUFFICIENT_SIGNAL")
    return {
        "level": RULE_COMPARISON_NOT_READY,
        "supports_budget_delta": False,
        "reasons": reasons,
    }


def _aggregate_levels(levels: List[str]) -> str:
    if not levels:
        return RULE_COMPARISON_NOT_READY
    if any(x == RULE_COMPARISON_NOT_READY for x in levels):
        if any(x == RULE_COMPARISON_FULL for x in levels):
            return RULE_COMPARISON_PARTIAL
        if any(x == RULE_COMPARISON_PARTIAL for x in levels):
            return RULE_COMPARISON_PARTIAL
        return RULE_COMPARISON_NOT_READY
    if all(x == RULE_COMPARISON_FULL for x in levels):
        return RULE_COMPARISON_FULL
    if RULE_COMPARISON_FULL in levels:
        return RULE_COMPARISON_PARTIAL
    return RULE_COMPARISON_PARTIAL


def evaluate_policy_comparison_readiness(
    *,
    benefit_rules: Optional[List[Dict[str, Any]]] = None,
    exclusions: Optional[List[Dict[str, Any]]] = None,
    draft_rule_candidates: Optional[List[Dict[str, Any]]] = None,
    normalized: Optional[Dict[str, Any]] = None,
    policy_version_id: Optional[str] = None,
    db: Any = None,
) -> Dict[str, Any]:
    """
    Policy-level readiness plus per-rule evaluations.

    Provide either:
    - ``normalized`` dict with benefit_rules / exclusions / draft_rule_candidates, or
    - ``benefit_rules`` + ``exclusions`` (+ optional draft_rule_candidates), or
    - ``policy_version_id`` + ``db`` to load Layer 2 from the database.
    """
    if normalized is not None:
        br = list(normalized.get("benefit_rules") or [])
        ex = list(normalized.get("exclusions") or [])
        dc = list(normalized.get("draft_rule_candidates") or [])
    elif policy_version_id and db is not None:
        try:
            br = db.list_policy_benefit_rules(str(policy_version_id))
        except Exception:
            br = []
        try:
            from .policy_hr_rule_override_layer import merge_benefit_rules_for_comparison_engine

            br = merge_benefit_rules_for_comparison_engine(db, str(policy_version_id), br)
        except Exception:
            pass
        try:
            ex = db.list_policy_exclusions(str(policy_version_id))
        except Exception:
            ex = []
        dc = []
    else:
        br = list(benefit_rules or [])
        ex = list(exclusions or [])
        dc = list(draft_rule_candidates or [])

    rule_evaluations: List[Dict[str, Any]] = []

    for r in br:
        ev = evaluate_rule_comparison_readiness(r, rule_kind="benefit_rule")
        rule_evaluations.append(
            {
                "kind": "benefit_rule",
                "id": r.get("id"),
                "benefit_key": r.get("benefit_key"),
                **ev,
            }
        )

    for e in ex:
        ev = evaluate_rule_comparison_readiness(e, rule_kind="exclusion")
        rule_evaluations.append(
            {
                "kind": "exclusion",
                "id": e.get("id"),
                "benefit_key": e.get("benefit_key"),
                "domain": e.get("domain"),
                **ev,
            }
        )

    for d in dc:
        ev = evaluate_rule_comparison_readiness(d, rule_kind="draft_candidate")
        rule_evaluations.append(
            {
                "kind": "draft_candidate",
                "clause_index": d.get("clause_index"),
                "clause_id": d.get("clause_id"),
                "benefit_key": d.get("candidate_service_key"),
                **ev,
            }
        )

    by_key: Dict[str, List[str]] = defaultdict(list)
    for item in rule_evaluations:
        bk = (item.get("benefit_key") or "").strip()
        if not bk:
            continue
        by_key[bk].append(item.get("level") or RULE_COMPARISON_NOT_READY)

    per_benefit_key: Dict[str, Any] = {}
    required: Set[str] = set(EMPLOYEE_COMPARISON_REQUIRED_BENEFIT_KEYS)
    for req in sorted(required):
        levels = by_key.get(req, [])
        agg = _aggregate_levels(levels)
        per_benefit_key[req] = {
            "level": agg,
            "rule_levels": levels,
        }

    req_levels = [per_benefit_key[k]["level"] for k in sorted(required)]
    if not rule_evaluations:
        policy_level = RULE_COMPARISON_NOT_READY
    elif all(l == RULE_COMPARISON_FULL for l in req_levels):
        policy_level = RULE_COMPARISON_FULL
    elif all(l == RULE_COMPARISON_NOT_READY for l in req_levels):
        policy_level = RULE_COMPARISON_NOT_READY
    else:
        policy_level = RULE_COMPARISON_PARTIAL

    counts = {"full": 0, "partial": 0, "not_ready": 0}
    for item in rule_evaluations:
        lv = item.get("level")
        if lv in counts:
            counts[lv] += 1

    comparison_ready_strict = policy_level == RULE_COMPARISON_FULL

    return {
        "policy_level": policy_level,
        "per_benefit_key": per_benefit_key,
        "rule_evaluations": rule_evaluations,
        "counts_by_level": counts,
        "comparison_ready": comparison_ready_strict,
        "comparison_ready_strict": comparison_ready_strict,
        "supports_any_budget_delta": any(r.get("supports_budget_delta") for r in rule_evaluations),
    }


def enrich_resolved_benefits_with_rule_comparison(
    db: Any,
    policy_version_id: Optional[str],
    benefits: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Attach per-benefit ``rule_comparison_readiness`` by re-loading source Layer-2 rules
    (no DB migration on resolved_assignment_policy_benefits).
    """
    if not policy_version_id or not benefits:
        return benefits
    try:
        rules = db.list_policy_benefit_rules(str(policy_version_id))
        try:
            from .policy_hr_rule_override_layer import merge_benefit_rules_for_comparison_engine

            rules = merge_benefit_rules_for_comparison_engine(db, str(policy_version_id), rules)
        except Exception:
            pass
    except Exception:
        return benefits
    by_id = {str(r.get("id")): r for r in rules if r.get("id")}
    out: List[Dict[str, Any]] = []
    for b in benefits:
        nb = dict(b)
        sr = b.get("source_rule_ids_json") or []
        rid = None
        if isinstance(sr, list) and sr:
            rid = sr[0]
        src = by_id.get(str(rid)) if rid is not None else None
        if src:
            nb["rule_comparison_readiness"] = evaluate_rule_comparison_readiness(src, rule_kind="benefit_rule")
        elif not b.get("included", True):
            nb["rule_comparison_readiness"] = {
                "level": RULE_COMPARISON_FULL,
                "supports_budget_delta": False,
                "reasons": ["RESOLVED_EXCLUDED"],
            }
        elif b.get("max_value") is not None or b.get("standard_value") is not None:
            nb["rule_comparison_readiness"] = {
                "level": RULE_COMPARISON_FULL,
                "supports_budget_delta": True,
                "reasons": ["RESOLVED_NUMERIC"],
            }
        else:
            nb["rule_comparison_readiness"] = {
                "level": RULE_COMPARISON_PARTIAL,
                "supports_budget_delta": False,
                "reasons": ["RESOLVED_COVERAGE_ONLY"],
            }
        out.append(nb)
    return out


def merge_version_comparison_readiness(
    existing: Dict[str, Any],
    *,
    benefit_rules: List[Dict[str, Any]],
    exclusions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Attach rule-level policy comparison to legacy version comparison payload (non-destructive)."""
    detail = evaluate_policy_comparison_readiness(benefit_rules=benefit_rules, exclusions=exclusions)
    out = dict(existing)
    out["rule_comparison_readiness"] = {
        "policy_level": detail["policy_level"],
        "per_benefit_key": detail["per_benefit_key"],
        "counts_by_level": detail["counts_by_level"],
        "supports_any_budget_delta": detail["supports_any_budget_delta"],
    }
    out["rule_evaluations"] = detail["rule_evaluations"]
    # Align comparison_ready with strict full policy if we want engine parity
    out["comparison_ready_strict"] = detail["comparison_ready_strict"]
    return out
