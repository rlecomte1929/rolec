"""Timeline / operational relocation tasks — defaults from case context + summary helpers."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# ── S5 wiring: workstream_id → (milestone_types, timing, criticality) ────────
# Maps WorkstreamRequirement.workstream_id from FamilyPropagator to the
# milestone_type(s) that should be seeded into case_milestones, along with
# a days_before_move anchor and criticality label.
#
# Order within each tuple is: (milestone_type, title, owner, criticality, sort_order, days_before_move)
# Mirror timing from WorkstreamRequirement.typical_lead_time_weeks × 7.
_WORKSTREAM_MILESTONE_SPECS: Dict[str, List[Tuple[str, str, str, str, int, int]]] = {
    "partner_mvv": [
        (
            "task_partner_mvv",
            "Apply for Dutch MVV (partner family entry visa)",
            "joint",
            "critical",
            12,          # sort_order — before main visa prep (sort_order 40)
            84,          # days_before_move (12 weeks)
        ),
    ],
    "partner_family_visa": [
        (
            "task_partner_family_visa",
            "Apply for partner / family reunification visa",
            "joint",
            "critical",
            13,
            70,          # 10 weeks
        ),
    ],
    "dependent_visa": [
        (
            "task_dependent_visa",
            "Apply for dependent / spouse visa",
            "joint",
            "normal",
            48,          # after main visa submit (sort_order 45)
            42,          # 6 weeks
        ),
    ],
    "spouse_work_authorization": [
        (
            "task_spouse_work_permit",
            "Obtain spouse / partner work authorisation",
            "joint",
            "normal",
            42,
            63,          # 9 weeks
        ),
    ],
    "school_enrollment": [
        (
            "task_school_research",
            "Research and shortlist schools",
            "employee",
            "normal",
            27,          # pre-departure, after family details (sort_order 10)
            84,
        ),
        (
            "task_school_application",
            "Submit school applications",
            "employee",
            "normal",
            43,          # immigration phase, alongside visa
            56,          # 8 weeks
        ),
    ],
}

# ── S5/P2 wiring: regime_id → ordered list of (milestone_type, title, owner, criticality, sort_order, days_before_move)
# Maps ImmigrationRegimeResult.regime_id → concrete milestone specs to seed.
# Timing anchored to days_before_move from compute_default_milestones base anchor.
_REGIME_MILESTONE_SPECS: Dict[str, List[Tuple[str, str, str, str, int, int]]] = {
    "us_l1b": [
        ("task_l1b_support_letter",   "Prepare US entity L1B support letter",           "hr",       "critical", 6,  140),
        ("task_l1b_petition_prep",    "Prepare I-129 L1B petition package",              "hr",       "critical", 7,  133),
        ("task_l1b_petition_filing",  "File I-129 L1B petition with USCIS",              "hr",       "critical", 5,  126),
        ("task_l1b_visa_interview",   "Complete DS-160 and attend US consulate interview","employee", "critical", 20,  56),
        ("task_l1b_port_of_entry",    "US port of entry — CBP inspection and I-94",      "employee", "critical", 2,    0),  # arrival day
        ("task_l1b_ssn",              "Apply for US Social Security Number",             "employee", "normal",   6,  -14), # 2 weeks after move
    ],
    "japan_coe": [
        ("task_japan_coe_prep",       "Prepare COE application",                         "hr",       "critical", 6,  112),
        ("task_japan_coe_visa",       "Apply for Japan work visa using COE",             "employee", "critical", 6,   28),
        ("task_japan_residence_card", "Collect Residence Card at port of entry",         "employee", "critical", 3,    0),  # arrival day
        ("task_japan_municipal_reg",  "Register at municipal office and obtain My Number","employee","critical", 3,  -14),
    ],
    "eu_free_movement": [
        ("task_eu_registration",      "Register as EU/EEA resident at local authority",  "employee", "normal",   4,  -21), # 3 weeks after move
    ],
    "uk_skilled_worker": [
        ("task_uk_cos_request",           "Request Certificate of Sponsorship (CoS) from employer",   "hr",       "critical", 6,   70),
        ("task_uk_visa_application",      "Submit UK Skilled Worker visa application online",          "employee", "critical", 7,   49),
        ("task_uk_biometric_appointment", "Attend biometric appointment at UKVCAS centre",             "employee", "critical", 5,   35),
        ("task_uk_brp_collection",        "Collect Biometric Residence Permit (BRP) on arrival",      "employee", "critical", 2,    0),  # arrival day
        ("task_uk_right_to_work_check",   "Complete employer right-to-work verification",              "hr",       "critical", 3,   -7), # 1 week after arrival
    ],
}

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
    # ── S5 wiring additions (all optional — backward-compatible) ────────────
    contract_type: Optional[str] = None,
    family_profile: Optional[Dict[str, Any]] = None,
    destination_country: Optional[str] = None,
    origin_country: Optional[str] = None,
    # ── P2 wiring addition ───────────────────────────────────────────────────
    nationality: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Compute default operational tasks for a case (inserted into case_milestones when none exist).
    Dates are anchored on target move / arrival when available.

    S5 additions:
    - contract_type gates which phases are included (domestic_move suppresses immigration,
      short_term_project suppresses logistics + post_arrival).
    - family_profile triggers additional family workstream milestones via FamilyPropagator.
    """
    _ = case_id
    services = set(selected_services or [])
    base = _parse_move_anchor(case_draft, target_move_date)

    # ── Determine active phases (S5) ─────────────────────────────────────────
    active_phases: Optional[set] = None
    if contract_type and contract_type not in ("unknown", ""):
        try:
            from ...services.plan_scope import active_phases_for_case_type
            from ...relocation_plan_task_library import TASK_BY_MILESTONE_TYPE
            _active_list = active_phases_for_case_type(contract_type)
            active_phases = set(_active_list)
            _task_by_mt = TASK_BY_MILESTONE_TYPE
        except ImportError:
            active_phases = None
            _task_by_mt = {}
    else:
        try:
            from ...relocation_plan_task_library import TASK_BY_MILESTONE_TYPE
            _task_by_mt = TASK_BY_MILESTONE_TYPE
        except ImportError:
            _task_by_mt = {}

    def _phase_allowed(milestone_type: str) -> bool:
        """Return True if this milestone_type's phase is in the active set (or if unknown)."""
        if active_phases is None:
            return True
        entry = _task_by_mt.get(milestone_type)  # type: ignore[name-defined]
        if entry is None:
            return True   # unknown milestone_type → fail open
        return entry.phase_key in active_phases

    result: List[Dict[str, Any]] = []
    for spec in OPERATIONAL_TASK_DEFAULTS:
        mt = spec["milestone_type"]
        if mt == "task_provider_coordination" and not services:
            continue
        if not _phase_allowed(mt):
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

    # ── Inject family workstream milestones (S5) ─────────────────────────────
    if family_profile:
        try:
            from ...services.family_propagation import FamilyPropagator
            propagator = FamilyPropagator()
            workstreams = propagator.get_required_workstreams(
                family_profile=family_profile,
                destination_country=destination_country,
                origin_country=origin_country,
            )
            existing_milestone_types = {r["milestone_type"] for r in result}
            for ws in workstreams:
                specs_for_ws = _WORKSTREAM_MILESTONE_SPECS.get(ws.workstream_id, [])
                for (mt, title, owner, criticality, sort_order, days_before) in specs_for_ws:
                    if mt in existing_milestone_types:
                        continue   # already present (shouldn't happen but guard it)
                    if active_phases is not None:
                        entry = _task_by_mt.get(mt)  # type: ignore[name-defined]
                        if entry and entry.phase_key not in active_phases:
                            continue  # suppressed phase
                    target: Optional[str] = None
                    if base:
                        target = (base - timedelta(days=days_before)).strftime("%Y-%m-%d")
                    result.append({
                        "milestone_type": mt,
                        "title": title,
                        "description": ws.reason,
                        "sort_order": sort_order,
                        "target_date": target,
                        "status": "pending",
                        "owner": owner,
                        "criticality": criticality,
                        "notes": ws.notes or None,
                    })
                    existing_milestone_types.add(mt)
        except ImportError:
            pass  # family_propagation not available — skip silently

    # ── Inject immigration-regime milestones (P2) ─────────────────────────────
    # Runs whenever nationality or destination_country is known.
    if destination_country or nationality:
        try:
            from ...services.immigration_regime import ImmigrationRegimeRouter
            regime_router = ImmigrationRegimeRouter()
            regime = regime_router.detect_regime(
                nationality=nationality,
                destination_country=destination_country,
                origin_country=origin_country,
                contract_type=contract_type,
            )
            specs_for_regime = _REGIME_MILESTONE_SPECS.get(regime.regime_id, [])
            existing_milestone_types_set = {r["milestone_type"] for r in result}
            for (mt, title, owner, criticality, sort_order, offset_days) in specs_for_regime:
                if mt in existing_milestone_types_set:
                    continue
                if active_phases is not None:
                    entry = _task_by_mt.get(mt)  # type: ignore[name-defined]
                    if entry and entry.phase_key not in active_phases:
                        continue
                target: Optional[str] = None
                if base:
                    if offset_days >= 0:
                        target = (base - timedelta(days=offset_days)).strftime("%Y-%m-%d")
                    else:
                        # Negative offset = days AFTER move date
                        target = (base + timedelta(days=abs(offset_days))).strftime("%Y-%m-%d")
                result.append({
                    "milestone_type": mt,
                    "title": title,
                    "description": regime.notes or None,
                    "sort_order": sort_order,
                    "target_date": target,
                    "status": "pending",
                    "owner": owner,
                    "criticality": criticality,
                    "notes": None,
                })
                existing_milestone_types_set.add(mt)
        except ImportError:
            pass  # immigration_regime not available — skip silently

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
