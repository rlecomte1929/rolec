"""Timeline / operational relocation tasks — defaults from case context + summary helpers."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

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
    # Return / repatriation — dates anchored on assignment end, not move date.
    # Seeded at submit only when contract_type=repatriation; otherwise the
    # 6-month sweep appends these rows when today is in [end-182d, end).
    {
        "milestone_type": "task_return_review",
        "title": "End-of-assignment review",
        "description": "HR and the employee plan the return: next role, timing, and what the return covers.",
        "owner": "hr",
        "criticality": "normal",
        "sort_order": 200,
        "days_before_end": 182,
    },
    {
        "milestone_type": "task_return_shipment",
        "title": "Return move & storage release",
        "description": "Book the return shipment and release anything left in storage at origin.",
        "owner": "employee",
        "criticality": "normal",
        "sort_order": 210,
        "days_before_end": 56,
    },
    {
        "milestone_type": "task_return_host_tax",
        "title": "File the final host-country tax return",
        "description": "Settle the final host-country tax filing before leaving.",
        "owner": "employee",
        "criticality": "critical",
        "sort_order": 220,
        "days_before_end": 42,
    },
    {
        "milestone_type": "task_return_host_dereg",
        "title": "De-register locally in the host country",
        "description": "De-register your address / residence and close or convert local accounts.",
        "owner": "employee",
        "criticality": "normal",
        "sort_order": 230,
        "days_before_end": 28,
    },
    {
        "milestone_type": "task_return_lease",
        "title": "Close the host-country lease and recover the deposit",
        "description": "End the host lease on the assignment end date and recover the deposit.",
        "owner": "employee",
        "criticality": "normal",
        "sort_order": 240,
        "days_before_end": 30,
    },
    {
        "milestone_type": "task_return_home_reg",
        "title": "Re-register in the home country",
        "description": "Re-establish home-country residence: address, healthcare, and tax residence.",
        "owner": "employee",
        "criticality": "normal",
        "sort_order": 250,
        "days_after_end": 14,
    },
    {
        "milestone_type": "task_return_social",
        "title": "Social security & pension switch-back",
        "description": "Move social-security and pension cover back to the home scheme; close any A1 / certificate of coverage.",
        "owner": "employee",
        "criticality": "normal",
        "sort_order": 260,
        "days_after_end": 21,
    },
    {
        "milestone_type": "task_return_benefits",
        "title": "Reinstate home-country benefits",
        "description": "Payroll, healthcare, and pension need to switch back to the home scheme.",
        "owner": "joint",
        "criticality": "normal",
        "sort_order": 270,
        "days_before_end": 14,
    },
    {
        "milestone_type": "task_return_career",
        "title": "Career reintegration",
        "description": "Agree the next role and reporting line before the employee lands home.",
        "owner": "joint",
        "criticality": "normal",
        "sort_order": 280,
        "days_before_end": 90,
    },
    {
        "milestone_type": "task_return_closeout",
        "title": "Return case close-out",
        "description": "HR marks the assignment as repatriated and archives the return record.",
        "owner": "hr",
        "criticality": "normal",
        "sort_order": 290,
        "days_after_end": 0,
    },
]

# Stable milestone_type → title for cross-linking from HR readiness / intake (keep in sync with OPERATIONAL_TASK_DEFAULTS).
TRACKER_TASK_TITLES: Dict[str, str] = {
    str(row["milestone_type"]): str(row["title"])
    for row in OPERATIONAL_TASK_DEFAULTS
    if isinstance(row, dict) and row.get("milestone_type") and row.get("title")
}


def add_months(d: date, months: int) -> date:
    """Calendar-month addition that clamps the day to the target month's last day."""
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    last = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, last))


def derive_assignment_end_date(
    start: Optional[date],
    months: Optional[int],
) -> Optional[date]:
    """assignment_end_date = start + expectedDurationMonths. Never defaults to today."""
    if start is None or months is None or int(months) <= 0:
        return None
    return add_months(start, int(months))


def _parse_date_value(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        text = str(value).strip()
        if not text:
            return None
        if "T" in text:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def parse_assignment_start_from_draft(case_draft: Optional[Dict[str, Any]]) -> Optional[date]:
    draft = case_draft or {}
    ac = draft.get("assignmentContext") or {}
    assignment = draft.get("assignment") or {}
    for value in (
        assignment.get("startDate"),
        assignment.get("start_date"),
        ac.get("contractStartDate"),
        ac.get("startDate"),
        (draft.get("relocationBasics") or {}).get("targetMoveDate"),
        (draft.get("relocationBasics") or {}).get("target_move_date"),
    ):
        parsed = _parse_date_value(value)
        if parsed is not None:
            return parsed
    return None


def parse_expected_duration_months(case_draft: Optional[Dict[str, Any]]) -> Optional[int]:
    draft = case_draft or {}
    ac = draft.get("assignmentContext") or {}
    assignment = draft.get("assignment") or {}
    raw = ac.get("expectedDurationMonths")
    if raw is None:
        raw = assignment.get("expectedDurationMonths")
    try:
        months = int(raw) if raw is not None and str(raw).strip() != "" else None
    except (TypeError, ValueError):
        return None
    return months if months is not None and months > 0 else None


def _parse_assignment_end(case_draft: Optional[Dict[str, Any]]) -> Optional[datetime]:
    """End-date datetime for return-task anchors. None when start or duration is missing."""
    end = derive_assignment_end_date(
        parse_assignment_start_from_draft(case_draft),
        parse_expected_duration_months(case_draft),
    )
    if end is None:
        return None
    return datetime(end.year, end.month, end.day)


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


# Steps that exist ONLY because an immigration application is being filed. If no
# application is being filed, they are not "optional" — they do not exist.
_IMMIGRATION_ONLY_TASKS = frozenset({
    "task_immigration_review",   # "Book counsel or vendor review as required for the route."
    "task_visa_docs_prep",       # "Prepare visa / work permit application pack"
    "task_visa_submit",          # "Submit visa / work permit application"
    "task_biometrics",           # "Book biometrics / appointment"
})

# Steps that still apply without an immigration file, but whose default copy is
# written around one. Reword; do not drop. An EU citizen still needs their ID (for
# the Anmeldung, the bank, the lease) and still has to book a flight.
_NON_IMMIGRATION_COPY = {
    "task_passport_upload": (
        "Upload passport or national ID",
        "A clear scan of your passport or national identity card. You will need it for local "
        "registration, opening a bank account and signing a lease — not for a visa application.",
    ),
    "task_travel_plan": (
        "Plan travel",
        "Flights and arrival logistics aligned with your start date.",
    ),
}


def _immigration_applies(
    *,
    nationality: Optional[str],
    destination_country: Optional[str],
    origin_country: Optional[str],
    contract_type: Optional[str],
) -> bool:
    """True unless we POSITIVELY know no immigration application is required.

    Two ways to know:
      1. origin == destination. No border is crossed, so no immigration process can
         apply. A verifiable FACT, not a label — the purpose/move-type fields have
         proved untrustworthy, but two country codes can be compared.
      2. The immigration regime resolves to eu_free_movement.

    Anything else — including an unresolvable nationality — returns True and keeps
    the full visa track. If we cannot positively know, we do not suppress.
    """
    from .requirements_country_key import to_iso

    origin_iso = to_iso(origin_country)
    dest_iso = to_iso(destination_country)
    if origin_iso and dest_iso and origin_iso == dest_iso:
        return False

    if not (destination_country or nationality):
        return True  # nothing to reason from → keep the demanding track

    try:
        from .immigration_regime import ImmigrationRegimeRouter

        regime = ImmigrationRegimeRouter().detect_regime(
            nationality=nationality,
            destination_country=destination_country,
            origin_country=origin_country,
            contract_type=contract_type,
        )
        return regime.regime_id != "eu_free_movement"
    except ImportError:
        return True  # fail safe



# ── [AIQ-1867] Corridor pathway steps ────────────────────────────────────────────
#
# Andrea (ES→IE, Venezuelan, family of 4) sees "Prepare visa / work permit application
# pack", "Submit visa / work permit application" and "Book biometrics". Her actual route is
# a Critical Skills Employment Permit, then a long-stay 'D' visa, then IRP registration at
# Burgh Quay within 90 days, then PPSN, then a Revenue RPN before her first payslip. That
# journey is authored in corridors/ES_IE/pathways/CSEP_2026/v1.yaml and #1929 already reads
# it — but only on the roadmap_builder path. The milestone-backed plan view
# (/api/relocation-plans/{case}/view) never saw it, which is the surface she actually opens.
#
# This reuses roadmap_corridor_overlay rather than adding a second YAML reader: one gate on
# nationality class, one set of supersession rules, one provenance block.
#
# Phase, not track. The overlay assigns UI tracks (visa/family/settlement); milestones need a
# PHASE_ORDER key, and "which phase" is a different question from "which lane" — IRP happens
# after she lands, PPSN after that.
_CORRIDOR_STEP_PHASE: Dict[str, str] = {
    "JOB_OFFER_CONTRACT": "pre_departure",
    "EMPLOYMENT_PERMIT_APPLICATION": "immigration",
    "EMPLOYMENT_PERMIT_GRANTED": "immigration",
    "D_VISA_APPLICATION": "immigration",
    "D_VISA_GRANTED": "immigration",
    "TRAVEL_TO_IE": "logistics",
    "IRP_REGISTRATION": "arrival",
    "PPSN": "post_arrival",
    "REVENUE_REGISTRATION": "post_arrival",
    "BANK_ACCOUNT": "post_arrival",
    "HEALTH_SETUP": "post_arrival",
    "FAMILY_REGISTRATION": "post_arrival",
    "STAMP4_ELIGIBILITY": "post_arrival",
}


#: Generic milestones a corridor's authored immigration steps replace. Named explicitly and
#: kept deliberately narrow: the corridor tells the employee to file a Critical Skills
#: Employment Permit and then a 'D' visa, so "Prepare visa / work permit application pack"
#: and "Submit visa / work permit application" are the same work described vaguely, and
#: biometrics are part of the visa appointment. `task_immigration_review` is NOT here — a
#: counsel or vendor review is still a real, separate step on a curated route.
_CORRIDOR_SUPERSEDED_GENERIC = frozenset({
    "task_visa_docs_prep",
    "task_visa_submit",
    "task_biometrics",
})



#: Pathways whose step_graph order is NOT chronological, so position cannot place a step.
#: RETURNING_EEA_CITIZEN_2026 (NO_FR) lists `A0_DEPART_NO` first and then 29 steps, but
#: several of those are Norwegian EXIT tasks that must happen BEFORE departure —
#: "Preserve BankID before deregistration disables it" is the clearest. Deriving from
#: position would tell a leaver to do it after they have landed in France, which is worse
#: than saying nothing. It gets the generic scaffold until someone authors its phases.
_PATHWAYS_NOT_PHASEABLE_BY_POSITION = frozenset({"RETURNING_EEA_CITIZEN_2026"})


def _phases_from_arrival_anchor(
    steps: Sequence[Dict[str, Any]],
) -> Dict[str, str]:
    """Place every step by POSITION relative to the pathway's arrival anchor.

    Each pathway marks exactly one step ``arrival_anchor``. Measured across all 11: it sits
    mid-sequence in ES_IE and IN_DE (the permit routes, where paperwork precedes travel) and
    is the FIRST step in the other nine, which are register-on-arrival free-movement routes.
    Both shapes place correctly by position — everything after travel is post-arrival. That removes the need to know 82 step ids by name across
    the ten non-ES_IE corridors (NO_FR alone declares 30), which is why nine of them served
    the generic scaffold despite having an authored journey.

    Returns ``{}`` when no anchor is present, which the caller treats as "do not render
    this pathway at all".

    Coarser than the explicit map on purpose: there is no generic signal for "this step is
    immigration". ``conditional_on`` is not one — CSEP's EMPLOYMENT_PERMIT_APPLICATION and
    BLUECARD's VISA_APPLICATION both declare none — and the overlay's _IMMIGRATION_GATED is
    a hardcoded CSEP set. A corridor earns the finer split by being added to
    _CORRIDOR_STEP_PHASE, deliberately, when someone has reviewed its journey.
    """
    pathway = ""
    if steps:
        pathway = str(((steps[0].get("provenance") or {}).get("pathway")) or "")
    if pathway in _PATHWAYS_NOT_PHASEABLE_BY_POSITION:
        return {}

    anchor_at: Optional[int] = None
    for i, st in enumerate(steps):
        if st.get("arrival_anchor"):
            anchor_at = i
            break
    if anchor_at is None:
        return {}

    out: Dict[str, str] = {}
    for i, st in enumerate(steps):
        sid = str(st.get("step_id") or "").strip()
        if not sid:
            continue
        if i < anchor_at:
            out[sid] = "pre_departure"
        elif i == anchor_at:
            out[sid] = "logistics"
        else:
            out[sid] = "post_arrival"
    return out


def _corridor_milestones(
    case_draft: Optional[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], frozenset]:
    """Milestones from the case corridor's authored pathway, and the generic milestone_types
    they supersede.

    Returns ``([], frozenset())`` whenever no pathway applies — an unknown corridor, a free
    mover on a corridor whose steps are all immigration-gated, or any failure inside the
    overlay. The generic scaffold is the fallback and must stay intact in every one of those
    cases; this only ever REPLACES steps it has a curated answer for.
    """
    try:
        from .roadmap_corridor_overlay import corridor_overlay
    except ImportError:  # pragma: no cover - defensive, module is in-tree
        return [], frozenset()

    overlay = corridor_overlay({"draft": case_draft or {}})
    if not overlay:
        return [], frozenset()
    steps = overlay.get("corridor_steps") or []
    if not steps:
        return [], frozenset()

    derived = _phases_from_arrival_anchor(steps)
    if not derived:
        # No pivot to place steps against. Rendering them anyway is how 13 of IN_DE's 14
        # steps once landed in a single pre_departure block — worse than the generic
        # scaffold it replaced. Fall back wholesale instead.
        return [], frozenset()

    rows: List[Dict[str, Any]] = []
    for idx, step in enumerate(steps, start=1):
        sid = str(step.get("step_id") or "").strip()
        if not sid:
            continue
        # The explicit map wins where it has an opinion: it is the only thing that puts a
        # step in the `immigration` phase, which is the distinction AIQ-1867 asked for.
        phase = _CORRIDOR_STEP_PHASE.get(sid) or derived[sid]
        # {phase}_corridor_{NN} — parsed by relocation_plan_service so the step lands in its
        # real phase block. Deliberately not the {phase}_ai_{NN} form: this is curated data.
        rows.append(
            {
                "milestone_type": f"{phase}_corridor_{idx:02d}",
                "title": step.get("name") or sid,
                "description": None,
                "sort_order": 500 + idx,
                "target_date": None,
                "status": "pending",
                "owner": step.get("responsible_party") or "joint",
                # A blocking step is one nothing downstream can proceed without.
                "criticality": "high" if step.get("blocking") else "normal",
                "notes": None,
            }
        )
    # The overlay's own `superseded_generic_keys` are roadmap_builder STEP keys
    # ("permit", "police", "tax") — a different namespace from case_milestones.
    # milestone_type. Translating here rather than widening the overlay keeps each
    # consumer owning the vocabulary it actually serves.
    #
    # Conditional on the corridor having really supplied immigration steps. A pathway that
    # resolves but contributes no permit/visa step (an EEA national on this corridor: every
    # immigration step is gated off) must NOT strip the generic visa track — that would
    # silently delete the only immigration guidance a mover has, which is the one failure
    # mode worse than showing generic copy.
    # Supersede when the corridor describes pre-departure work of its own — that is the
    # same ground "Prepare visa / work permit application pack" gestures at, and showing
    # both is worse than showing only the generic one because the employee cannot tell
    # which is real. Measured: without this, IN_DE rendered its "D-visa application at the
    # German mission in Bangalore" alongside the generic pack.
    #
    # Keyed on POSITION (anything before the arrival anchor), not on the `immigration`
    # phase, because only the explicit map ever produces that phase — the derived rule is
    # coarser, so an `immigration`-only trigger fires for ES_IE alone.
    #
    # A free-movement corridor contributes nothing before travel, so it never strips the
    # visa track. That is deliberate: a third-country national routed onto an EEA pathway
    # keeps the generic guidance, because the pathway does not describe their route.
    pre_anchor = [r for r in rows
                  if r["milestone_type"].split("_corridor_")[0] in ("immigration", "pre_departure")]
    supersedes: frozenset = _CORRIDOR_SUPERSEDED_GENERIC if pre_anchor else frozenset()
    return rows, supersedes


def build_return_milestones(end: Optional[date]) -> List[Dict[str, Any]]:
    """Return-phase operational rows, optionally dated from ``end``.

    Used by ``compute_default_milestones`` (via OPERATIONAL_TASK_DEFAULTS) and
    by the 6-month sweep so both writers share one spec list.
    """
    end_dt = datetime(end.year, end.month, end.day) if end is not None else None
    rows: List[Dict[str, Any]] = []
    for spec in OPERATIONAL_TASK_DEFAULTS:
        mt = str(spec["milestone_type"])
        if not mt.startswith("task_return_"):
            continue
        target: Optional[str] = None
        if end_dt is not None:
            dbe = spec.get("days_before_end")
            dae = spec.get("days_after_end")
            if dbe is not None:
                target = (end_dt - timedelta(days=int(dbe))).strftime("%Y-%m-%d")
            elif dae is not None:
                target = (end_dt + timedelta(days=int(dae))).strftime("%Y-%m-%d")
        rows.append(
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
    return rows


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
            from .plan_scope import active_phases_for_case_type
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
        """Return True if this milestone_type's phase is in the active set (or if unknown).

        Return-phase tasks are NEVER fail-open: without an explicit ``return`` in
        active_phases they would clutter every outbound LTA at submit.
        """
        entry = _task_by_mt.get(milestone_type)  # type: ignore[name-defined]
        is_return = (entry is not None and entry.phase_key == "return") or str(
            milestone_type
        ).startswith("task_return_")
        if is_return:
            return active_phases is not None and "return" in active_phases
        if active_phases is None:
            return True
        if entry is None:
            return True   # unknown milestone_type → fail open
        return entry.phase_key in active_phases

    # ── Does an immigration application apply at all? ─────────────────────────
    #
    # Resolved BEFORE the operational defaults are laid down, because it decides
    # whether some of them may exist.
    #
    # In production this roadmap told an EU national relocating to Germany, in the
    # same list: "Register as EU/EEA resident — EU/EEA free movement: no work permit
    # required" (#4) AND "Submit visa / work permit application" (#45). The generator
    # knew the regime and served the visa track anyway, because _REGIME_MILESTONE_SPECS
    # only ever ADDS. Nothing subtracted.
    #
    # Asymmetric on purpose: we suppress the visa track ONLY when we positively know
    # it cannot apply. An unknown or unresolvable nationality keeps it. Over-showing a
    # visa step to an EU citizen is a poor experience; under-showing one to a person
    # who genuinely needs it is a harm.
    immigration_applies = _immigration_applies(
        nationality=nationality,
        destination_country=destination_country,
        origin_country=origin_country,
        contract_type=contract_type,
    )

    # ── [AIQ-1867] Corridor pathway, resolved BEFORE the generic loop ────────
    #
    # Resolved first because it decides which generic steps may exist at all: a curated
    # route that names the Critical Skills Employment Permit and the 'D' visa supersedes
    # "Prepare visa / work permit application pack". Showing both would be worse than
    # showing only the generic one — the employee cannot tell which is real.
    corridor_rows, superseded_generic = _corridor_milestones(case_draft)

    end_anchor = _parse_assignment_end(case_draft)

    result: List[Dict[str, Any]] = []
    for spec in OPERATIONAL_TASK_DEFAULTS:
        mt = spec["milestone_type"]
        if mt == "task_provider_coordination" and not services:
            continue
        if not _phase_allowed(mt):
            continue
        if not immigration_applies and mt in _IMMIGRATION_ONLY_TASKS:
            continue  # no application is being filed — the step does not exist
        if mt in superseded_generic:
            continue  # the corridor answers this step specifically
        target: Optional[str] = None
        dbe = spec.get("days_before_end")
        dae = spec.get("days_after_end")
        if end_anchor is not None and (dbe is not None or dae is not None):
            if dbe is not None:
                target = (end_anchor - timedelta(days=int(dbe))).strftime("%Y-%m-%d")
            elif dae is not None:
                target = (end_anchor + timedelta(days=int(dae))).strftime("%Y-%m-%d")
        elif base:
            dbm = spec.get("days_before_move")
            dam = spec.get("days_after_move")
            if dbm is not None:
                target = (base - timedelta(days=int(dbm))).strftime("%Y-%m-%d")
            elif dam is not None:
                target = (base + timedelta(days=int(dam))).strftime("%Y-%m-%d")
        title = spec["title"]
        description = spec.get("description")
        if not immigration_applies:
            # These two steps still apply — an EU citizen needs their ID for the
            # Anmeldung, and still has to book a flight — but their COPY is written
            # around a visa file they will never open. Reword rather than drop.
            reworded = _NON_IMMIGRATION_COPY.get(mt)
            if reworded:
                title, description = reworded
        result.append(
            {
                "milestone_type": mt,
                "title": title,
                "description": description,
                "sort_order": spec["sort_order"],
                "target_date": target,
                "status": "pending",
                "owner": spec.get("owner", "joint"),
                "criticality": spec.get("criticality", "normal"),
                "notes": None,
            }
        )

    result.extend(corridor_rows)

    # ── Inject family workstream milestones (S5) ─────────────────────────────
    if family_profile:
        try:
            from .family_propagation import FamilyPropagator
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
            from .immigration_regime import ImmigrationRegimeRouter
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
