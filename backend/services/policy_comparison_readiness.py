"""
Employee service comparison gate (Layer 2).

Derives whether the published policy_version is structurally ready for the
wizard comparison engine: each comparison benefit key must have at least one
benefit_rule row so resolution never falls through to speculative
\"no rule\" messaging.

See docs/policy/comparison-readiness-and-fallback.md and
docs/policy/minimum-normalized-policy-schema.md (ComparisonReadiness).
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger(__name__)

# Short TTL: collapses duplicate readiness checks in one page load without hiding HR publish fixes long.
_READINESS_CACHE_TTL_SEC = 15.0
_readiness_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def invalidate_comparison_readiness_cache(policy_version_id: Optional[str]) -> None:
    """Call after publish/archive so employees do not see stale comparison_ready for ~TTL."""
    if not policy_version_id:
        return
    _readiness_cache.pop(str(policy_version_id), None)

# Benefit keys required for employee **cost comparison** (PackageSummary caps + core movers/schools/housing).
# Full wizard/service comparison also touches banking_setup and insurance; see
# docs/policy/comparison-readiness-and-fallback.md for how this relates to the minimum schema.
EMPLOYEE_COMPARISON_REQUIRED_BENEFIT_KEYS: Set[str] = {
    "temporary_housing",
    "schooling",
    "shipment",
}


def _parse_metadata(rule: Dict[str, Any]) -> Dict[str, Any]:
    raw = rule.get("metadata_json") or rule.get("metadata") or {}
    if isinstance(raw, str):
        try:
            return json.loads(raw) if raw.strip() else {}
        except Exception:
            return {}
    return raw if isinstance(raw, dict) else {}


def _rule_has_decision_signal(rule: Dict[str, Any]) -> bool:
    """
    True if the rule can drive a non-vacuous comparison outcome:
    numeric cap/limit, percent/amount on rule, or explicit approval flag in metadata.
    Excluded / not-allowed-only rows still count as long as they exist (handled by key coverage).
    """
    meta = _parse_metadata(rule)
    av = rule.get("amount_value")
    if av is not None:
        try:
            if float(av) > 0:
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
    if meta.get("approval_required") is True:
        return True
    if meta.get("allowed") is False:
        return True
    return False


def evaluate_version_comparison_readiness(db: Any, policy_version_id: Optional[str]) -> Dict[str, Any]:
    """
    Return { comparison_ready, comparison_blockers, partial_numeric_coverage }.

    comparison_ready requires:
      - policy_version_id is set
      - published row exists with that id and status == 'published'
      - for every benefit_key in EMPLOYEE_COMPARISON_REQUIRED_BENEFIT_KEYS, at least one benefit_rule exists
        for that key with _rule_has_decision_signal (numeric / approval / explicit exclusion)

    Results are cached in-process per policy_version_id for ~120s to reduce duplicate work on
    employee policy + budget + services calls in the same session.
    """
    blockers: List[str] = []

    if not policy_version_id:
        return {
            "comparison_ready": False,
            "comparison_blockers": ["MISSING_POLICY_VERSION"],
            "partial_numeric_coverage": False,
        }

    cache_key = str(policy_version_id)
    now = time.monotonic()
    cached = _readiness_cache.get(cache_key)
    if cached and (now - cached[0]) < _READINESS_CACHE_TTL_SEC:
        return cached[1]

    try:
        version = db.get_policy_version(str(policy_version_id))
    except Exception as exc:
        log.warning("comparison_readiness get_policy_version failed version_id=%s exc=%s", policy_version_id, exc)
        version = None

    if not version:
        return {
            "comparison_ready": False,
            "comparison_blockers": ["MISSING_POLICY_VERSION"],
            "partial_numeric_coverage": False,
        }

    status = (version.get("status") or "").lower()
    if status != "published":
        return {
            "comparison_ready": False,
            "comparison_blockers": ["NOT_PUBLISHED"],
            "partial_numeric_coverage": False,
        }

    try:
        rules = db.list_policy_benefit_rules(str(policy_version_id))
    except Exception as exc:
        log.warning("comparison_readiness list_policy_benefit_rules failed version_id=%s exc=%s", policy_version_id, exc)
        rules = []

    keys_found: Set[str] = set()
    keys_with_signal: Set[str] = set()
    for r in rules:
        bk = (r.get("benefit_key") or "").strip()
        if not bk:
            continue
        if bk not in EMPLOYEE_COMPARISON_REQUIRED_BENEFIT_KEYS:
            continue
        keys_found.add(bk)
        if _rule_has_decision_signal(r):
            keys_with_signal.add(bk)

    for req in sorted(EMPLOYEE_COMPARISON_REQUIRED_BENEFIT_KEYS):
        if req not in keys_found:
            blockers.append(f"MISSING_COMPARISON_CATEGORY:{req}")
        elif req not in keys_with_signal:
            blockers.append(f"COVERED_WITHOUT_DECISION_FIELDS:{req}")

    ready = len(blockers) == 0
    out = {
        "comparison_ready": ready,
        "comparison_blockers": blockers,
        "partial_numeric_coverage": False,
    }
    _readiness_cache[cache_key] = (now, out)
    return out
