import uuid
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .guidance_markdown import render_guidance_markdown


def build_profile_snapshot(draft: Dict[str, Any], dossier_answers: Dict[str, Any], destination_country: Optional[str]) -> Dict[str, Any]:
    basics = draft.get("relocationBasics") or {}
    employee = draft.get("employeeProfile") or {}
    assignment = draft.get("assignmentContext") or {}
    family = draft.get("familyMembers") or {}

    snapshot = {
        "origin_country": basics.get("originCountry"),
        "destination_country": destination_country or basics.get("destCountry"),
        "move_date": basics.get("targetMoveDate"),
        "employment_type": assignment.get("contractType"),
        "employer_country": assignment.get("employerCountry"),
        "dependents": basics.get("hasDependents"),
        "nationality": employee.get("nationality"),
        "current_location": employee.get("residenceCountry"),
        "notes": assignment.get("notes") if isinstance(assignment, dict) else None,
        "dossier_answers": dossier_answers,
        "family_members": family,
    }
    return snapshot


def _eval_guidance_rule(applies_if: Optional[Dict[str, Any]], snapshot: Dict[str, Any]) -> bool:
    if not applies_if:
        return True
    if "and" in applies_if:
        return all(_eval_guidance_rule(r, snapshot) for r in applies_if.get("and", []))
    if "or" in applies_if:
        return any(_eval_guidance_rule(r, snapshot) for r in applies_if.get("or", []))
    if "not" in applies_if:
        return not _eval_guidance_rule(applies_if.get("not"), snapshot)
    if "!" in applies_if:
        return not _eval_guidance_rule(applies_if.get("!"), snapshot)
    if "==" in applies_if:
        left, right = applies_if["=="]
        return _resolve_var(left, snapshot) == right
    if "in" in applies_if:
        left, right = applies_if["in"]
        val = _resolve_var(left, snapshot)
        if isinstance(right, list):
            return val in right
        return False
    return True


def _resolve_var(expr: Any, snapshot: Dict[str, Any]) -> Any:
    if isinstance(expr, dict) and "var" in expr:
        key = expr["var"]
        if isinstance(key, str) and "." in key:
            current: Any = snapshot
            for part in key.split("."):
                if not isinstance(current, dict):
                    return None
                current = current.get(part)
            return current
        return snapshot.get(key)
    return expr


def _extract_vars(applies_if: Optional[Dict[str, Any]]) -> List[str]:
    if not applies_if:
        return []
    if isinstance(applies_if, dict):
        if "var" in applies_if:
            return [applies_if["var"]]
        vars_found: List[str] = []
        for _, v in applies_if.items():
            vars_found.extend(_extract_vars(v))
        return vars_found
    if isinstance(applies_if, list):
        vars_found: List[str] = []
        for item in applies_if:
            vars_found.extend(_extract_vars(item))
        return vars_found
    return []


MIN_PLAN_ITEMS = 6
MIN_CHECKLIST_ITEMS = 8


def _select_baseline_injections(
    baseline_rules: List[Dict[str, Any]],
    selected_rules: List[Dict[str, Any]],
    needed: int,
) -> List[Dict[str, Any]]:
    if needed <= 0:
        return []
    selected_ids = {r.get("id") for r in selected_rules}
    candidates = [r for r in baseline_rules if r.get("id") not in selected_ids]
    by_phase: Dict[str, List[Dict[str, Any]]] = {}
    for rule in candidates:
        by_phase.setdefault(rule.get("phase") or "other", []).append(rule)
    injections: List[Dict[str, Any]] = []
    for phase in ("pre_move", "arrival", "first_90_days", "first_tax_year"):
        if needed <= 0:
            break
        phase_rules = by_phase.get(phase) or []
        if phase_rules:
            injections.append(phase_rules[0])
            needed -= 1
    if needed > 0:
        remaining = [r for r in candidates if r not in injections]
        injections.extend(remaining[:needed])
    return injections


def enforce_citations(rules: List[Dict[str, Any]], docs_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    usable: List[Dict[str, Any]] = []
    not_covered: List[str] = []
    for rule in rules:
        citations = rule.get("citations") or []
        if not citations or any(c not in docs_by_id for c in citations):
            not_covered.append(rule.get("title") or rule.get("rule_key") or "Unknown rule")
            continue
        usable.append(rule)
    return {"usable": usable, "not_covered": not_covered}


def build_plan(usable_rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    items = []
    for rule in usable_rules:
        items.append({
            "phase": rule.get("phase"),
            "category": rule.get("category"),
            "title": rule.get("title"),
            "description_md": rule.get("guidance_md"),
            "citations": rule.get("citations"),
            "rule": rule.get("rule_meta"),
        })
    return {"items": items, "assumptions": None, "key_risks": None}


def _relative_label(phase: str) -> str:
    if phase == "pre_move":
        return "4–8 weeks before move"
    if phase == "arrival":
        return "within first 1–2 weeks after arrival"
    if phase == "first_90_days":
        return "within first 30–90 days"
    if phase == "first_tax_year":
        return "during the first tax year"
    return "timing to be confirmed"


def _compute_due_date(move_date: Optional[str], phase: str) -> Optional[str]:
    if not move_date:
        return None
    try:
        base = datetime.fromisoformat(move_date)
    except Exception:
        return None
    if phase == "pre_move":
        return (base - timedelta(days=28)).date().isoformat()
    if phase == "arrival":
        return (base + timedelta(days=14)).date().isoformat()
    if phase == "first_90_days":
        return (base + timedelta(days=60)).date().isoformat()
    if phase == "first_tax_year":
        return None
    return None


def build_checklist(plan: Dict[str, Any], move_date: Optional[str]) -> Dict[str, Any]:
    items = []
    for item in plan.get("items", []):
        phase = item.get("phase")
        items.append({
            "phase": phase,
            "title": item.get("title"),
            "description": item.get("description_md"),
            "due_date": _compute_due_date(move_date, phase),
            "relative_to_move": _relative_label(phase),
            "citations": item.get("citations"),
            "rule": item.get("rule"),
        })
    return {"items": items}


def collect_sources(usable_rules: List[Dict[str, Any]], docs_by_id: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    sources = []
    for rule in usable_rules:
        for doc_id in rule.get("citations") or []:
            if doc_id in seen:
                continue
            seen.add(doc_id)
            doc = docs_by_id.get(doc_id)
            if not doc:
                continue
            sources.append({
                "doc_id": doc_id,
                "title": doc.get("title"),
                "url": doc.get("source_url"),
                "publisher": doc.get("publisher"),
            })
    return sources


def build_coverage(snapshot: Dict[str, Any], plan: Dict[str, Any], sources: List[Dict[str, Any]], not_covered: List[str]) -> Dict[str, Any]:
    score = 0
    missing_info: List[str] = []
    domains = set()

    if snapshot.get("origin_country") and snapshot.get("destination_country"):
        score += 20
    else:
        if not snapshot.get("origin_country"):
            missing_info.append("origin_country")
        if not snapshot.get("destination_country"):
            missing_info.append("destination_country")

    if snapshot.get("move_date"):
        score += 10
    else:
        missing_info.append("move_date")

    if snapshot.get("employment_type"):
        score += 10
    else:
        missing_info.append("employment_type")

    if not snapshot.get("dossier_answers", {}).get("sg.pass_type_known") and not snapshot.get("dossier_answers", {}).get("us.visa_known"):
        missing_info.append("visa_type")

    for item in plan.get("items", []):
        if item.get("category"):
            domains.add(item.get("category"))
    score += min(40, 10 * len(domains))

    if len(sources) >= 3:
        score += 10

    if snapshot.get("origin_country") and snapshot.get("destination_country") and snapshot.get("origin_country") == snapshot.get("destination_country"):
        not_covered.append("Origin and destination are the same; confirm if relocation guidance is needed.")

    return {
        "score": max(0, min(100, score)),
        "domains_covered": sorted(list(domains)),
        "missing_info": missing_info,
        "not_covered": not_covered,
    }


def _hash_pack(snapshot: Dict[str, Any], rule_set: List[Dict[str, Any]]) -> str:
    payload = {
        "snapshot": snapshot,
        "rules": [{"rule_key": r["rule_key"], "version": r["version"], "injected_for_minimum": r["injected_for_minimum"]} for r in rule_set],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_guidance_pack(
    case_id: str,
    user_id: str,
    destination_country: str,
    draft: Dict[str, Any],
    dossier_answers: Dict[str, Any],
    rules: List[Dict[str, Any]],
    docs_by_id: Dict[str, Dict[str, Any]],
    guidance_mode: str,
) -> Dict[str, Any]:
    snapshot = build_profile_snapshot(draft, dossier_answers, destination_country)
    active_rules = [r for r in rules if r.get("is_active", True)]

    rule_logs: List[Dict[str, Any]] = []
    matched: List[Dict[str, Any]] = []
    baseline: List[Dict[str, Any]] = []
    not_covered: List[str] = []

    for rule in active_rules:
        applies_if = rule.get("applies_if")
        evaluation_result = _eval_guidance_rule(applies_if, snapshot)
        citations = rule.get("citations") or []
        citations_valid = bool(citations) and all(c in docs_by_id for c in citations)
        if not citations_valid:
            not_covered.append(rule.get("title") or rule.get("rule_key") or "Unknown rule")
        if rule.get("is_baseline"):
            if citations_valid:
                baseline.append(rule)
        else:
            if evaluation_result and citations_valid:
                matched.append(rule)
        vars_used = _extract_vars(applies_if)
        snapshot_subset = {k: _resolve_var({"var": k}, snapshot) for k in vars_used}
        rule_logs.append({
            "rule_id": rule.get("id"),
            "rule_key": rule.get("rule_key"),
            "rule_version": rule.get("version", 1),
            "pack_id": rule.get("pack_id"),
            "pack_version": rule.get("pack_version", 1),
            "applies_if": applies_if,
            "evaluation_result": evaluation_result,
            "was_baseline": bool(rule.get("is_baseline")),
            "injected_for_minimum": False,
            "citations": citations,
            "snapshot_subset": snapshot_subset,
        })

    baseline_sorted = sorted(baseline, key=lambda r: r.get("baseline_priority", 100))
    usable_rules = list(matched)
    baseline_injected = 0
    if guidance_mode == "demo" and len(usable_rules) < MIN_PLAN_ITEMS:
        needed = max(0, MIN_PLAN_ITEMS - len(usable_rules))
        injections = _select_baseline_injections(baseline_sorted, usable_rules, needed)
        for rule in injections:
            rule["injected_for_minimum"] = True
            usable_rules.append(rule)
            baseline_injected += 1
        if baseline_injected > 0:
            not_covered.append("Demo mode: baseline rules were added due to limited profile specificity.")
        if len(usable_rules) < MIN_PLAN_ITEMS:
            not_covered.append("We do not have enough curated baseline steps for this corridor yet.")
    elif guidance_mode == "strict":
        not_covered.append("Strict mode: output reflects only matched curated rules.")

    # Attach provenance metadata to each rule
    rule_set: List[Dict[str, Any]] = []
    for rule in usable_rules:
        meta = {
            "rule_id": rule.get("id"),
            "rule_key": rule.get("rule_key"),
            "version": rule.get("version", 1),
            "pack_id": rule.get("pack_id"),
            "pack_version": rule.get("pack_version", 1),
            "is_baseline": bool(rule.get("is_baseline")),
            "injected_for_minimum": bool(rule.get("injected_for_minimum")),
        }
        rule["rule_meta"] = meta
        rule_set.append(meta)
        for log in rule_logs:
            if log["rule_id"] == meta["rule_id"]:
                log["injected_for_minimum"] = meta["injected_for_minimum"]

    plan = build_plan(usable_rules)
    checklist = build_checklist(plan, snapshot.get("move_date"))

    # Ensure checklist minimum of 8 items (demo mode only)
    if guidance_mode == "demo" and len(checklist["items"]) < MIN_CHECKLIST_ITEMS:
        existing = checklist["items"]
        supplemental = []
        for item in plan.get("items", []):
            if len(existing) + len(supplemental) >= MIN_CHECKLIST_ITEMS:
                break
            supplemental.append({
                "phase": item.get("phase"),
                "title": f"Confirm: {item.get('title')}",
                "description": item.get("description_md"),
                "due_date": _compute_due_date(snapshot.get("move_date"), item.get("phase")),
                "relative_to_move": _relative_label(item.get("phase")),
                "citations": item.get("citations"),
                "rule": item.get("rule"),
            })
        checklist["items"] = existing + supplemental

    sources = collect_sources(usable_rules, docs_by_id)
    coverage = build_coverage(snapshot, plan, sources, not_covered)
    coverage["guidance_mode"] = guidance_mode
    coverage["baseline_injected_count"] = baseline_injected
    coverage["matched_rules_count"] = len(matched)
    markdown = render_guidance_markdown(snapshot, plan, checklist, sources, coverage)
    pack_hash = _hash_pack(snapshot, rule_set)
    return {
        "snapshot": snapshot,
        "plan": plan,
        "checklist": checklist,
        "sources": sources,
        "not_covered": coverage["not_covered"],
        "coverage": coverage,
        "rule_set": rule_set,
        "pack_hash": pack_hash,
        "rule_logs": rule_logs,
        "markdown": markdown,
    }
