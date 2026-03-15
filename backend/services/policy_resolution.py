"""
Policy resolution: transforms published policy versions into concrete assignment packages.

Resolves benefit rules, exclusions, and applicability conditions for a specific assignment
using assignment context (type, family status, destination, duration, tier).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .policy_taxonomy import ASSIGNMENT_TYPE_MAP, FAMILY_STATUS_MAP, get_benefit_meta

log = logging.getLogger(__name__)


def _normalize_assignment_type(raw: Optional[str]) -> str:
    """Normalize assignment type to LTA, STA, etc."""
    if not raw or not str(raw).strip():
        return "LTA"
    key = str(raw).lower().replace("-", "_").replace(" ", "_")
    return ASSIGNMENT_TYPE_MAP.get(key, raw.strip().upper()[:20])


def _normalize_family_status(raw: Optional[str]) -> str:
    """Normalize family status."""
    if not raw or not str(raw).strip():
        return "single"
    key = str(raw).lower().strip()
    return FAMILY_STATUS_MAP.get(key, key)


def extract_resolution_context(
    assignment: Dict[str, Any],
    case: Optional[Dict[str, Any]],
    profile: Optional[Dict[str, Any]],
    employee_profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Extract resolution context from assignment, case, and profiles.
    """
    ctx: Dict[str, Any] = {
        "assignment_type": "LTA",
        "family_status": "single",
        "family_size": 1,
        "destination_country": None,
        "destination_city": None,
        "duration_months": None,
        "accompanied_family": False,
        "tier": None,
        "children_count": 0,
        "has_spouse": False,
        "school_age_children": False,
    }

    # Prefer employee_profile (from employee_profiles) over case profile_json
    p = employee_profile or (profile or {})

    # Assignment type: from employees table, profile, or assignment metadata
    at = (
        assignment.get("assignment_type")
        or p.get("assignmentType")
        or p.get("primaryApplicant", {}).get("assignmentType")
        or p.get("movePlan", {}).get("assignmentType")
    )
    ctx["assignment_type"] = _normalize_assignment_type(at)

    # Family status and size
    spouse = p.get("spouse") or p.get("spousal", {})
    ctx["has_spouse"] = bool(spouse.get("fullName") or spouse.get("accompanying"))
    deps = p.get("dependents") or p.get("children") or []
    if isinstance(deps, list):
        ctx["children_count"] = len(deps)
    elif isinstance(deps, (int, float)):
        ctx["children_count"] = int(deps)
    ctx["family_size"] = 1 + (1 if ctx["has_spouse"] else 0) + ctx["children_count"]
    ctx["accompanied_family"] = ctx["family_size"] > 1

    fs = (
        p.get("maritalStatus")
        or p.get("familyStatus")
        or ("accompanied" if ctx["accompanied_family"] else "single")
    )
    ctx["family_status"] = _normalize_family_status(fs)

    # School age: check dependents ages
    for d in deps if isinstance(deps, list) else []:
        age = d.get("age") if isinstance(d, dict) else None
        if age is not None and 5 <= int(age) <= 18:
            ctx["school_age_children"] = True
            break

    # Destination
    mp = p.get("movePlan") or {}
    dest = mp.get("destination") or case.get("host_country") or ""
    if isinstance(dest, str) and "," in dest:
        parts = dest.split(",")
        ctx["destination_city"] = parts[0].strip() if parts else None
        ctx["destination_country"] = parts[-1].strip()[:2].upper() if parts else None
    elif dest:
        ctx["destination_country"] = str(dest)[:2].upper() if len(str(dest)) >= 2 else str(dest)

    # Duration
    dur = mp.get("duration") or p.get("assignmentDuration") or assignment.get("expected_duration_months")
    if dur:
        if isinstance(dur, (int, float)):
            ctx["duration_months"] = int(dur)
        elif isinstance(dur, str) and "month" in dur.lower():
            try:
                ctx["duration_months"] = int("".join(c for c in dur if c.isdigit()) or 12)
            except ValueError:
                ctx["duration_months"] = 12

    # Tier / band
    tier = (
        p.get("primaryApplicant", {}).get("employer", {}).get("jobLevel")
        or p.get("band")
        or p.get("tier")
        or assignment.get("tier")
    )
    ctx["tier"] = str(tier).strip() if tier else None

    return ctx


def _rule_applies_by_assignment_type(
    rule_id: str,
    assignment_type: str,
    assignment_applicability: List[Dict[str, Any]],
) -> bool:
    """True if benefit rule has no assignment restriction or assignment_type matches."""
    apps = [a for a in assignment_applicability if a.get("benefit_rule_id") == rule_id]
    if not apps:
        return True
    types_ok = [a.get("assignment_type") for a in apps if a.get("assignment_type")]
    if not types_ok:
        return True
    return assignment_type.upper() in [t.upper() for t in types_ok]


def _rule_applies_by_family_status(
    rule_id: str,
    family_status: str,
    family_applicability: List[Dict[str, Any]],
) -> bool:
    """True if benefit rule has no family restriction or family_status matches."""
    apps = [a for a in family_applicability if a.get("benefit_rule_id") == rule_id]
    if not apps:
        return True
    statuses_ok = [a.get("family_status") for a in apps if a.get("family_status")]
    if not statuses_ok:
        return True
    fs_lower = family_status.lower()
    return fs_lower in [s.lower() for s in statuses_ok]


def _evaluate_condition(
    cond: Dict[str, Any],
    ctx: Dict[str, Any],
) -> bool:
    """Evaluate a policy_rule_condition against context."""
    ctype = cond.get("condition_type", "")
    val = cond.get("condition_value_json") or {}
    if not isinstance(val, dict):
        return True

    if ctype == "assignment_type":
        allowed = val.get("assignment_types") or val.get("values") or []
        if not allowed:
            return True
        return ctx.get("assignment_type", "").upper() in [str(a).upper() for a in allowed]

    if ctype == "family_status":
        allowed = val.get("family_statuses") or val.get("values") or []
        if not allowed:
            return True
        return ctx.get("family_status", "").lower() in [str(a).lower() for a in allowed]

    if ctype == "duration_threshold":
        min_months = val.get("min_months") or val.get("min_duration")
        if min_months is None:
            return True
        dur = ctx.get("duration_months")
        if dur is None:
            return True
        return int(dur) >= int(min_months)

    if ctype == "accompanied_family":
        req = val.get("required", True)
        return ctx.get("accompanied_family", False) == req

    if ctype == "school_age_threshold":
        req = val.get("has_school_age", True)
        return ctx.get("school_age_children", False) == req

    if ctype == "remote_location":
        # If condition says remote required, we'd need destination to be in remote list
        return True

    if ctype == "localization_exclusion":
        # Excludes certain countries; we'd check destination_country
        excluded = val.get("excluded_countries") or []
        dest = ctx.get("destination_country")
        if not dest or not excluded:
            return True
        return dest.upper() not in [str(c).upper() for c in excluded]

    return True


def _is_benefit_excluded(
    benefit_key: str,
    domain: str,
    exclusions: List[Dict[str, Any]],
    ctx: Dict[str, Any],
) -> bool:
    """Check if benefit is excluded by any exclusion rule."""
    for ex in exclusions:
        ex_bk = ex.get("benefit_key")
        ex_domain = (ex.get("domain") or "").lower()
        if ex_bk and ex_bk != benefit_key:
            continue
        if ex_domain == "all" or ex_domain == "general":
            return True
        if ex_domain == "tax" and benefit_key in ("tax",):
            return True
        if ex_bk == benefit_key:
            return True
    return False


def _get_tier_override(
    benefit_rule_id: str,
    tier: Optional[str],
    tier_overrides: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Get tier override limits for benefit rule if tier matches."""
    if not tier:
        return None
    for to in tier_overrides:
        if to.get("benefit_rule_id") != benefit_rule_id:
            continue
        tk = (to.get("tier_key") or "").lower()
        if tk and tier.lower() in (tk, tk.replace(" ", ""), tk.replace("band", "")):
            return to.get("override_limits_json") or {}
    return None


def _meta(r: Dict[str, Any], key: str, default: Any = None) -> Any:
    m = r.get("metadata_json") or r.get("metadata") or {}
    if not isinstance(m, dict):
        return default
    return m.get(key, default)


def resolve_policy_for_assignment(
    db: Any,
    assignment_id: str,
    assignment: Dict[str, Any],
    case: Optional[Dict[str, Any]],
    profile: Optional[Dict[str, Any]],
    employee_profile: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Resolve published policy for assignment. Returns resolved policy dict or None if no policy.
    """
    ctx = extract_resolution_context(assignment, case, profile, employee_profile)
    case_id = assignment.get("case_id")
    canonical_case_id = assignment.get("canonical_case_id") or case_id

    # Get company_id from case, HR user's profile, or employee's profile
    company_id = case.get("company_id") if case else None
    if not company_id and assignment.get("hr_user_id"):
        profile_rec = db.get_profile_record(assignment["hr_user_id"])
        if profile_rec:
            company_id = profile_rec.get("company_id")
    if not company_id and assignment.get("employee_user_id"):
        emp_profile = db.get_profile_record(assignment["employee_user_id"])
        if emp_profile:
            company_id = emp_profile.get("company_id")
    if not company_id:
        log.warning(
            "policy_resolution: no company_id for assignment %s (case=%s, hr_user=%s, emp_user=%s)",
            assignment_id,
            bool(case),
            assignment.get("hr_user_id"),
            assignment.get("employee_user_id"),
        )
        # #region agent log
        try:
            import os, json as _json, time
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".cursor", "debug-2c6040.log")
            with open(path, "a") as f:
                f.write(_json.dumps({"sessionId": "2c6040", "hypothesisId": "H2", "location": "policy_resolution.resolve_policy_for_assignment", "message": "company_id is None", "data": {"assignment_id": assignment_id}, "timestamp": int(time.time() * 1000)}) + "\n")
        except Exception:
            pass
        # #endregion
        return None

    # Get company policy that has a published version (try any policy for this company)
    result = db.get_company_policy_with_published_version(company_id)
    # #region agent log
    try:
        import os, json as _json, time
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".cursor", "debug-2c6040.log")
        with open(path, "a") as f:
            f.write(_json.dumps({"sessionId": "2c6040", "hypothesisId": "H3", "location": "policy_resolution.resolve_policy_for_assignment", "message": "get_company_policy_with_published_version", "data": {"company_id": company_id, "has_published_version": result is not None}, "timestamp": int(time.time() * 1000)}) + "\n")
    except Exception:
        pass
    # #endregion
    if not result:
        policies = db.list_company_policies(company_id)
        log.info(
            "policy_resolution: no published policy for company %s (company has %s policies, none published)",
            company_id,
            len(policies),
        )
        return None

    policy, version = result
    policy_id = policy["id"]
    vid = version["id"]
    benefit_rules = db.list_policy_benefit_rules(vid)
    exclusions = db.list_policy_exclusions(vid)
    evidence_reqs = db.list_policy_evidence_requirements(vid)
    conditions = db.list_policy_rule_conditions(vid)
    assignment_applicability = db.list_policy_assignment_applicability(vid)
    family_applicability = db.list_policy_family_applicability(vid)
    tier_overrides = db.list_policy_tier_overrides(vid)

    # Build evidence by benefit_rule_id
    evidence_by_rule: Dict[str, List[str]] = {}
    for ev in evidence_reqs:
        brid = ev.get("benefit_rule_id")
        items = ev.get("evidence_items_json") or []
        if isinstance(items, list):
            evidence_by_rule.setdefault(brid or "", []).extend(items)

    # Conditions by object
    conditions_by_object: Dict[tuple, List[Dict]] = {}
    for c in conditions:
        key = (c.get("object_type"), c.get("object_id"))
        conditions_by_object.setdefault(key, []).append(c)

    assignment_type = ctx["assignment_type"]
    family_status = ctx["family_status"]
    tier = ctx["tier"]

    resolved_benefits: List[Dict[str, Any]] = []
    resolved_exclusions: List[Dict[str, Any]] = []
    review_notes: List[str] = []
    resolution_status = "ok"

    # Apply exclusions to build exclusion list (global and benefit-specific)
    for ex in exclusions:
        domain = ex.get("domain") or "general"
        desc = ex.get("description") or ex.get("raw_text", "")[:200]
        resolved_exclusions.append({
            "benefit_key": ex.get("benefit_key"),
            "domain": domain,
            "description": desc,
            "source_rule_ids_json": [ex.get("id")],
        })

    # Resolve each benefit rule
    for rule in benefit_rules:
        rid = rule.get("id")
        bk = rule.get("benefit_key")
        if not bk:
            continue

        # Check assignment type applicability
        if not _rule_applies_by_assignment_type(rid, assignment_type, assignment_applicability):
            continue

        # Check family status applicability
        if not _rule_applies_by_family_status(rid, family_status, family_applicability):
            continue

        # Evaluate conditions for this rule
        conds = conditions_by_object.get(("benefit_rule", rid), [])
        if conds:
            if not all(_evaluate_condition(cond, ctx) for cond in conds):
                continue  # Skip this rule - at least one condition failed

        # Check exclusions
        excluded = _is_benefit_excluded(bk, "general", exclusions, ctx)
        if excluded:
            resolved_benefits.append({
                "benefit_key": bk,
                "included": False,
                "min_value": None,
                "standard_value": None,
                "max_value": None,
                "currency": rule.get("currency"),
                "amount_unit": rule.get("amount_unit"),
                "frequency": rule.get("frequency"),
                "approval_required": False,
                "evidence_required_json": [],
                "exclusions_json": [{"domain": "excluded", "description": "Excluded by policy"}],
                "condition_summary": "Excluded",
                "source_rule_ids_json": [rid],
            })
            continue

        # Allowed - compute values
        allowed = _meta(rule, "allowed", True)
        if not allowed:
            resolved_benefits.append({
                "benefit_key": bk,
                "included": False,
                "min_value": None,
                "standard_value": None,
                "max_value": None,
                "currency": rule.get("currency"),
                "amount_unit": rule.get("amount_unit"),
                "frequency": rule.get("frequency"),
                "approval_required": False,
                "evidence_required_json": [],
                "exclusions_json": [],
                "condition_summary": "Not allowed",
                "source_rule_ids_json": [rid],
            })
            continue

        # Base values
        std = rule.get("amount_value") or _meta(rule, "standard_value")
        minv = _meta(rule, "min_value")
        maxv = _meta(rule, "max_value")
        approval = _meta(rule, "approval_required", False) or rule.get("review_status") == "edited"
        ev_items = evidence_by_rule.get(rid, [])

        # Tier override
        override = _get_tier_override(rid, tier, tier_overrides)
        if override:
            std = override.get("standard_value") or override.get("amount") or std
            minv = override.get("min_value") or minv
            maxv = override.get("max_value") or maxv

        cond_summary_parts = [f"{assignment_type}", f"{family_status}"]
        if tier:
            cond_summary_parts.append(f"tier:{tier}")

        resolved_benefits.append({
            "benefit_key": bk,
            "included": True,
            "min_value": minv,
            "standard_value": std,
            "max_value": maxv,
            "currency": rule.get("currency") or "USD",
            "amount_unit": rule.get("amount_unit"),
            "frequency": rule.get("frequency"),
            "approval_required": bool(approval),
            "evidence_required_json": ev_items if isinstance(ev_items, list) else list(ev_items),
            "exclusions_json": [],
            "condition_summary": ", ".join(cond_summary_parts),
            "source_rule_ids_json": [rid],
        })

    # Persist
    rid = db.upsert_resolved_assignment_policy(
        assignment_id=assignment_id,
        case_id=case_id,
        company_id=company_id,
        policy_id=policy_id,
        policy_version_id=vid,
        canonical_case_id=canonical_case_id,
        resolution_status=resolution_status,
        resolution_context=ctx,
        benefits=resolved_benefits,
        exclusions=resolved_exclusions,
    )

    # Fetch and return
    resolved = db.get_resolved_assignment_policy(assignment_id)
    if not resolved:
        return None
    resolved["benefits"] = db.list_resolved_policy_benefits(rid)
    resolved["exclusions"] = db.list_resolved_policy_exclusions(rid)
    resolved["policy"] = policy
    resolved["version"] = version
    resolved["resolution_context"] = ctx
    return resolved
