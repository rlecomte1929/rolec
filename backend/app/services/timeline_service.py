"""Timeline / operational relocation tasks — defaults from case context + summary helpers."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

# Practical relocation tasks (stored as case_milestones; linked to same case as readiness/checklist).
# milestone_type is stable for future sync with readiness checklist keys if needed.
# Phased plan metadata (task_code, phase_key, deps) lives in relocation_plan_task_library — keep types aligned.
OPERATIONAL_TASK_DEFAULTS: List[Dict[str, Any]] = [
    {
        "milestone_type": "task_profile_core",
        "title": "Confirm employee core profile",
        "description": "Verify legal name, contact, nationality, and job basics in the case record.",
        "owner": "employee",
        "criticality": "normal",
        "sort_order": 5,
        "days_before_move": 95,
    },
    {
        "milestone_type": "task_family_dependents",
        "title": "Confirm family / dependent details",
        "description": "Spouse and children (if any) recorded for immigration and benefits.",
        "owner": "joint",
        "criticality": "normal",
        "sort_order": 10,
        "days_before_move": 92,
    },
    {
        "milestone_type": "task_passport_upload",
        "title": "Upload passport copy",
        "description": "Clear scan of passport bio page for visa / work authorization.",
        "owner": "employee",
        "criticality": "critical",
        "sort_order": 15,
        "days_before_move": 88,
    },
    {
        "milestone_type": "task_employment_letter",
        "title": "Upload employment / assignment letter",
        "description": "Signed letter describing role, compensation, and assignment terms.",
        "owner": "employee",
        "criticality": "critical",
        "sort_order": 20,
        "days_before_move": 85,
    },
    {
        "milestone_type": "task_route_verify",
        "title": "Verify destination route",
        "description": "HR confirms origin → destination and assignment routing against policy.",
        "owner": "hr",
        "criticality": "normal",
        "sort_order": 25,
        "days_before_move": 80,
    },
    {
        "milestone_type": "task_hr_case_review",
        "title": "HR review of case data",
        "description": "Internal review of intake, documents, and policy fit before external filings.",
        "owner": "hr",
        "criticality": "critical",
        "sort_order": 30,
        "days_before_move": 75,
    },
    {
        "milestone_type": "task_immigration_review",
        "title": "Schedule immigration review",
        "description": "Book counsel or vendor review as required for the route.",
        "owner": "hr",
        "criticality": "normal",
        "sort_order": 35,
        "days_before_move": 70,
    },
    {
        "milestone_type": "task_visa_docs_prep",
        "title": "Prepare visa / work permit application pack",
        "description": "Compile forms and supporting documents per destination rules.",
        "owner": "joint",
        "criticality": "critical",
        "sort_order": 40,
        "days_before_move": 65,
    },
    {
        "milestone_type": "task_visa_submit",
        "title": "Submit visa / work permit application",
        "description": "Filing with authority or sponsor; capture reference numbers and deadlines.",
        "owner": "joint",
        "criticality": "critical",
        "sort_order": 45,
        "days_before_move": 55,
    },
    {
        "milestone_type": "task_biometrics",
        "title": "Book biometrics / appointment (if applicable)",
        "description": "Visa center or embassy appointments when required by the route.",
        "owner": "employee",
        "criticality": "normal",
        "sort_order": 50,
        "days_before_move": 45,
    },
    {
        "milestone_type": "task_temp_housing",
        "title": "Arrange temporary housing",
        "description": "Short-term accommodation before permanent housing is secured.",
        "owner": "employee",
        "criticality": "normal",
        "sort_order": 55,
        "days_before_move": 35,
    },
    {
        "milestone_type": "task_movers_shipment",
        "title": "Arrange movers / shipment",
        "description": "Quotes, inventory, insurance, and shipping dates.",
        "owner": "employee",
        "criticality": "normal",
        "sort_order": 60,
        "days_before_move": 28,
    },
    {
        "milestone_type": "task_travel_plan",
        "title": "Plan travel",
        "description": "Flights and arrival logistics aligned with visa validity and start date.",
        "owner": "employee",
        "criticality": "normal",
        "sort_order": 65,
        "days_before_move": 14,
    },
    {
        "milestone_type": "task_provider_coordination",
        "title": "Coordinate relocation providers",
        "description": "Engage approved vendors for housing, schools, or logistics as needed.",
        "owner": "provider",
        "criticality": "normal",
        "sort_order": 68,
        "days_before_move": 21,
    },
    {
        "milestone_type": "task_arrival_registration",
        "title": "Complete arrival registration",
        "description": "Local registration or residency steps required shortly after arrival.",
        "owner": "employee",
        "criticality": "normal",
        "sort_order": 70,
        "days_after_move": 3,
    },
    {
        "milestone_type": "task_tax_local_registration",
        "title": "Tax / local registration",
        "description": "Tax ID, social security, or host-country equivalents.",
        "owner": "employee",
        "criticality": "normal",
        "sort_order": 75,
        "days_after_move": 14,
    },
    {
        "milestone_type": "task_settling_in",
        "title": "Settle in — critical post-arrival steps",
        "description": "Bank, utilities, healthcare registration, and other blocking local setup.",
        "owner": "joint",
        "criticality": "normal",
        "sort_order": 80,
        "days_after_move": 21,
    },
]

# Stable milestone_type → title for cross-linking from HR readiness / intake (keep in sync with OPERATIONAL_TASK_DEFAULTS).
TRACKER_TASK_TITLES: Dict[str, str] = {
    str(row["milestone_type"]): str(row["title"])
    for row in OPERATIONAL_TASK_DEFAULTS
    if isinstance(row, dict) and row.get("milestone_type") and row.get("title")
}


def _parse_move_anchor(case_draft: Optional[Dict[str, Any]], target_move_date: Optional[str]) -> Optional[datetime]:
    basics = (case_draft or {}).get("relocationBasics", {}) or {}
    target = target_move_date or basics.get("targetMoveDate") or basics.get("target_move_date")
    if not target:
        return None
    try:
        if isinstance(target, str) and "T" in target:
            return datetime.fromisoformat(target.replace("Z", "+00:00"))
        if isinstance(target, str) and len(target) >= 10:
            return datetime.strptime(target[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    return None


def compute_default_milestones(
    case_id: str,
    case_draft: Optional[Dict[str, Any]] = None,
    selected_services: Optional[List[str]] = None,
    target_move_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Compute default operational tasks for a case (inserted into case_milestones when none exist).
    Dates are anchored on target move / arrival when available.
    """
    _ = case_id
    services = set(selected_services or [])
    base = _parse_move_anchor(case_draft, target_move_date)

    result: List[Dict[str, Any]] = []
    for spec in OPERATIONAL_TASK_DEFAULTS:
        mt = spec["milestone_type"]
        if mt == "task_provider_coordination" and not services:
            continue
        target: Optional[str] = None
        if base:
            dbm = spec.get("days_before_move")
            dam = spec.get("days_after_move")
            if dbm is not None:
                target = (base - timedelta(days=int(dbm))).strftime("%Y-%m-%d")
            elif dam is not None:
                target = (base + timedelta(days=int(dam))).strftime("%Y-%m-%d")
        result.append(
            {
                "milestone_type": mt,
                "title": spec["title"],
                "description": spec.get("description"),
                "sort_order": spec["sort_order"],
                "target_date": target,
                "status": "pending",
                "owner": spec.get("owner", "joint"),
                "criticality": spec.get("criticality", "normal"),
                "notes": None,
            }
        )
    return result


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def compute_timeline_summary(milestones: List[Dict[str, Any]], today: Optional[date] = None) -> Dict[str, int]:
    """Compact counts for tracker header (single pass, no extra queries)."""
    day = today or date.today()
    week_end = day + timedelta(days=7)
    total = len(milestones)
    completed = 0
    overdue = 0
    due_this_week = 0
    blocked = 0
    in_progress = 0
    for m in milestones:
        st = (m.get("status") or "pending").lower()
        if st == "done" or st == "skipped":
            completed += 1
            continue
        if st == "blocked":
            blocked += 1
        if st == "in_progress":
            in_progress += 1
        td = _parse_iso_date(m.get("target_date"))
        if td is None:
            continue
        if td < day:
            overdue += 1
        elif td <= week_end:
            due_this_week += 1
    return {
        "total": total,
        "completed": completed,
        "overdue": overdue,
        "due_this_week": due_this_week,
        "blocked": blocked,
        "in_progress": in_progress,
    }
