"""
Single HR Case Summary view-model for intake + route checklist + compliance (no second completeness engine).

Used only from GET /api/hr/assignments/{id} — same request as the case page.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from .app.services.timeline_service import TRACKER_TASK_TITLES

# Maps intake checkpoint keys → case_milestone.milestone_type (operational plan). Single source with timeline defaults.
INTAKE_KEY_TO_TRACKER_TYPE: Dict[str, str] = {
    "employee_name": "task_profile_core",
    "route_origin": "task_route_verify",
    "route_destination": "task_route_verify",
    "family_status": "task_family_dependents",
    "passport_details": "task_passport_upload",
    "job_level": "task_profile_core",
    "role_title": "task_profile_core",
    "timeline": "task_travel_plan",
    "doc_passport": "task_passport_upload",
    "doc_employment_letter": "task_employment_letter",
}


def _nz(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, (dict, list)):
        return bool(val)
    s = str(val).strip()
    if not s or s.lower() == "unknown":
        return False
    return True


def build_intake_checklist_items(profile: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Explicit tracked intake/document points aligned with ComplianceEngine + case essentials.
    Keys are stable for UI and docs; satisfied is deterministic from profile JSON only.
    """
    if not profile or not isinstance(profile, dict):
        specs = [
            ("employee_name", "Employee full name", "intake"),
            ("route_origin", "Origin (move plan)", "intake"),
            ("route_destination", "Destination (move plan)", "intake"),
            ("family_status", "Family / household status captured", "intake"),
            ("passport_details", "Passport details (number, country, or expiry)", "intake"),
            ("job_level", "Job level (policy / compliance checks)", "intake"),
            ("role_title", "Role / job title", "intake"),
            ("timeline", "Assignment start or planned arrival date", "intake"),
            ("doc_passport", "Passport scans (upload confirmed)", "documents"),
            ("doc_employment_letter", "Employment letter (upload confirmed)", "documents"),
        ]
        return [
            {
                "key": k,
                "label": lab,
                "satisfied": False,
                "category": cat,
                "linked_tracker_task_type": INTAKE_KEY_TO_TRACKER_TYPE.get(k),
            }
            for k, lab, cat in specs
        ]

    pa = profile.get("primaryApplicant") or {}
    if not isinstance(pa, dict):
        pa = {}
    mp = profile.get("movePlan") or {}
    if not isinstance(mp, dict):
        mp = {}
    cd = profile.get("complianceDocs") or {}
    if not isinstance(cd, dict):
        cd = {}
    emp = pa.get("employer") or {}
    if not isinstance(emp, dict):
        emp = {}
    asn = pa.get("assignment") or {}
    if not isinstance(asn, dict):
        asn = {}
    ppt = pa.get("passport") or {}
    if not isinstance(ppt, dict):
        ppt = {}
    spouse = profile.get("spouse") or {}
    if not isinstance(spouse, dict):
        spouse = {}
    deps = profile.get("dependents") or []
    if not isinstance(deps, list):
        deps = []

    fam_ok = (
        _nz(profile.get("maritalStatus"))
        or _nz(spouse.get("fullName"))
        or any(_nz(d.get("firstName")) for d in deps if isinstance(d, dict))
    )

    start_ok = _nz(asn.get("startDate"))
    arrival_ok = _nz(mp.get("targetArrivalDate"))
    if isinstance(mp.get("targetArrivalDate"), date):
        arrival_ok = True
    timeline_ok = start_ok or arrival_ok

    def _row(key: str, label: str, satisfied: bool, category: str) -> Dict[str, Any]:
        return {
            "key": key,
            "label": label,
            "satisfied": satisfied,
            "category": category,
            "linked_tracker_task_type": INTAKE_KEY_TO_TRACKER_TYPE.get(key),
        }

    items: List[Dict[str, Any]] = [
        _row("employee_name", "Employee full name", _nz(pa.get("fullName")), "intake"),
        _row("route_origin", "Origin (move plan)", _nz(mp.get("origin")), "intake"),
        _row("route_destination", "Destination (move plan)", _nz(mp.get("destination")), "intake"),
        _row("family_status", "Family / household status captured", fam_ok, "intake"),
        _row(
            "passport_details",
            "Passport details (number, country, or expiry)",
            _nz(ppt.get("number")) or _nz(ppt.get("issuingCountry")) or _nz(ppt.get("expiryDate")),
            "intake",
        ),
        _row("job_level", "Job level (policy / compliance checks)", _nz(emp.get("jobLevel")), "intake"),
        _row("role_title", "Role / job title", _nz(emp.get("roleTitle")), "intake"),
        _row("timeline", "Assignment start or planned arrival date", timeline_ok, "intake"),
        _row(
            "doc_passport",
            "Passport scans (upload confirmed)",
            cd.get("hasPassportScans") is True,
            "documents",
        ),
        _row(
            "doc_employment_letter",
            "Employment letter (upload confirmed)",
            cd.get("hasEmploymentLetter") is True,
            "documents",
        ),
    ]
    return items


def _format_deadline(profile: Optional[Dict[str, Any]]) -> Optional[str]:
    if not profile or not isinstance(profile, dict):
        return None
    mp = profile.get("movePlan") or {}
    pa = profile.get("primaryApplicant") or {}
    asn = (pa.get("assignment") or {}) if isinstance(pa, dict) else {}
    d = mp.get("targetArrivalDate") if isinstance(mp, dict) else None
    if not d and isinstance(asn, dict):
        d = asn.get("startDate")
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    s = str(d).strip()
    return s or None


def build_hr_case_readiness_ui(
    *,
    profile: Optional[Dict[str, Any]],
    intake_items: List[Dict[str, Any]],
    readiness_snap: Optional[Dict[str, Any]],
    compliance_report: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build CaseReadinessUi-compatible dict (validated in main)."""
    intake_total = len(intake_items)
    intake_done = sum(1 for x in intake_items if x.get("satisfied"))

    chk_applicable = False
    chk_done = None
    chk_total = None
    if readiness_snap and readiness_snap.get("resolved") and readiness_snap.get("checklist"):
        c = readiness_snap["checklist"]
        if isinstance(c, dict):
            t = int(c.get("total") or 0)
            if t > 0:
                chk_applicable = True
                chk_total = t
                chk_done = int(c.get("completed_or_waived") or 0)
    chk_pending = (chk_total - chk_done) if chk_applicable and chk_total is not None and chk_done is not None else None

    parts = [f"{intake_done} of {intake_total} intake & document checkpoints satisfied"]
    if chk_applicable and chk_total is not None and chk_done is not None:
        parts.append(f"{chk_done} of {chk_total} route checklist items completed (template)")

    completion_basis = "; ".join(parts)

    blocking: List[Dict[str, Any]] = []
    next_actions: List[Dict[str, Any]] = []

    for it in intake_items:
        if not it.get("satisfied"):
            blocking.append(
                {
                    "source": "intake",
                    "title": it.get("label") or it.get("key"),
                    "detail": "Missing or not confirmed in employee profile.",
                    "human_review_required": False,
                    "provenance_note": "Derived from assignment profile JSON (same fields as internal compliance checks).",
                    "linked_tracker_task_type": it.get("linked_tracker_task_type"),
                }
            )

    # One next-action per plan task type (links to relocation tracker — avoids contradicting per-task owner/due dates).
    plan_groups: Dict[str, List[str]] = {}
    for it in intake_items:
        if it.get("satisfied"):
            continue
        mt = it.get("linked_tracker_task_type")
        if not mt or not isinstance(mt, str):
            continue
        plan_groups.setdefault(mt, []).append(str(it.get("label") or it.get("key")))
    for mt in sorted(plan_groups.keys()):
        labels = plan_groups[mt]
        tt = TRACKER_TASK_TITLES.get(mt, mt)
        lbl_part = ", ".join(labels[:5])
        if len(labels) > 5:
            lbl_part += ", …"
        next_actions.append(
            {
                "title": f"Relocation plan: “{tt}” — covers: {lbl_part}. Open step 3 below for owner & due date.",
                "category": "plan",
                "linked_tracker_task_type": mt,
            }
        )

    if readiness_snap:
        if not readiness_snap.get("resolved"):
            reason = readiness_snap.get("reason") or "unknown"
            msg = readiness_snap.get("user_message") or f"Route readiness not available ({reason})."
            blocking.append(
                {
                    "source": "readiness",
                    "title": "Route / template readiness",
                    "detail": msg,
                    "human_review_required": True,
                    "provenance_note": "From case readiness resolution (destination, template store, migrations).",
                }
            )
            next_actions.append({"title": "Resolve destination and readiness template, or apply DB migrations.", "category": "readiness"})
        elif chk_pending and chk_pending > 0:
            blocking.append(
                {
                    "source": "readiness",
                    "title": f"Route checklist: {chk_pending} item(s) still open",
                    "detail": "Operational checklist from destination template — not legal verification.",
                    "human_review_required": bool(readiness_snap.get("human_review_required")),
                    "provenance_note": "Template checklist state; see Case readiness expand section.",
                }
            )

    if compliance_report:
        checks = compliance_report.get("checks") or []
        for c in checks:
            if not isinstance(c, dict):
                continue
            st = c.get("status")
            if st == "COMPLIANT":
                continue
            blocking.append(
                {
                    "source": "compliance",
                    "title": c.get("name") or c.get("id") or "Compliance check",
                    "detail": c.get("rationale"),
                    "human_review_required": bool(c.get("human_review_required")),
                    "provenance_note": c.get("rationale_legal_safety")
                    or "Internal policy rules (mobility_rules.json) — not immigration law.",
                }
            )
        for a in compliance_report.get("actions") or []:
            if isinstance(a, str):
                next_actions.append({"title": a, "category": "compliance"})
            elif isinstance(a, dict) and a.get("title"):
                next_actions.append({"title": a["title"], "category": "compliance"})

    trust_parts = []
    if compliance_report and compliance_report.get("disclaimer_legal"):
        trust_parts.append(compliance_report["disclaimer_legal"])
    if readiness_snap and readiness_snap.get("disclaimer_legal"):
        trust_parts.append(str(readiness_snap["disclaimer_legal"]))
    trust_banner = " ".join(trust_parts) if trust_parts else (
        "ReloPass does not verify immigration eligibility. Use official sources and qualified counsel."
    )

    comp_status = (compliance_report or {}).get("overallStatus")
    intake_incomplete = intake_done < intake_total
    rs = readiness_snap or {}
    resolved = bool(rs.get("resolved"))
    rreason = rs.get("reason")

    overall = "needs_review"
    overall_label = "Needs review"

    if profile is None or intake_incomplete:
        overall = "missing_information"
        overall_label = "Missing information"
    elif not resolved and rreason == "no_destination":
        overall = "missing_information"
        overall_label = "Missing information"
    elif not resolved:
        overall = "human_review_required"
        overall_label = "Human review required"
    elif comp_status == "NON_COMPLIANT" or comp_status == "NEEDS_REVIEW":
        overall = "needs_review"
        overall_label = "Needs review"
    elif chk_pending and chk_pending > 0:
        overall = "needs_review"
        overall_label = "Needs review"
    elif comp_status is None:
        overall = "needs_review"
        overall_label = "Needs review"
    elif comp_status == "COMPLIANT":
        if rs.get("human_review_required"):
            overall = "human_review_required"
            overall_label = "Human review required"
        else:
            overall = "ready"
            overall_label = "Ready"
    else:
        overall = "needs_review"
        overall_label = "Needs review"

    seen_titles = set()
    deduped_actions: List[Dict[str, Any]] = []
    for a in next_actions:
        t = (a.get("title") or "").strip()
        if not t or t in seen_titles:
            continue
        seen_titles.add(t)
        deduped_actions.append(a)
    next_actions = deduped_actions[:12]

    deadline_raw = _format_deadline(profile)
    next_deadline_display = None
    if deadline_raw:
        try:
            if "T" in deadline_raw:
                next_deadline_display = datetime.fromisoformat(deadline_raw.replace("Z", "+00:00")).strftime("%b %d, %Y")
            else:
                next_deadline_display = datetime.fromisoformat(deadline_raw[:10]).strftime("%b %d, %Y")
        except Exception:
            next_deadline_display = deadline_raw

    return {
        "overall_status": overall,
        "overall_label": overall_label,
        "completion_basis": completion_basis,
        "intake_satisfied": intake_done,
        "intake_total": intake_total,
        "checklist_satisfied": chk_done,
        "checklist_total": chk_total,
        "checklist_applicable": chk_applicable,
        "checklist_pending": chk_pending,
        "blocking_items": blocking,
        "next_actions": next_actions[:12],
        "trust_banner": trust_banner[:1200],
        "next_deadline_display": next_deadline_display,
    }
