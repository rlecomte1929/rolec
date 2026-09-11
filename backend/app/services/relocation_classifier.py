from typing import List, Literal, Optional

from pydantic import BaseModel

from .plan_scope import ALL_PHASES, REPATRIATION_PHASES, active_phases_for_case_type


# ── S3 SPIKE: extended CaseType ───────────────────────────────────────────────
# Original values are preserved exactly — no renames, no removals.
# New values are appended. Any existing code that switches on CaseType will
# hit its existing branches first; new values fall through to "else" / "unknown"
# in any unpatched switch until that code is updated separately.
CaseType = Literal[
    # ── original values (do not change) ──────────────────────────────────────
    "employee_sponsored",   # employer-sponsored international move, no further detail
    "remote_worker",        # working remotely from destination, no sponsorship
    "student",              # student visa route
    "self_employed",        # contractor / freelancer
    "unknown",              # not enough info to classify
    # ── S3 additions ─────────────────────────────────────────────────────────
    "lta",                  # long-term assignment (12–36 months), employer-sponsored
    "permanent_transfer",   # no planned return, full relocation
    "short_term_project",   # < 6 months, may qualify for visa-free or simplified permit
    "domestic_move",        # same country — immigration phase suppressed entirely
    "repatriation",         # returning to home country after a foreign assignment
]

# Phases suppressed relative to ALL_PHASES. Must agree with plan_scope:
# repatriation drops immigration and adds ``return`` via REPATRIATION_PHASES.
SUPPRESSED_PHASES: dict = {
    "domestic_move":        {"immigration"},
    "short_term_project":   {"logistics", "post_arrival"},
    "repatriation":         set(ALL_PHASES) - set(REPATRIATION_PHASES),
}

Priority = Literal["high", "medium", "low"]


class NextAction(BaseModel):
    key: str
    label: str
    priority: Priority


class CaseClassification(BaseModel):
    case_type: CaseType
    risk_flags: List[str]
    blockers: List[str]
    next_actions: List[NextAction]
    # S3 addition: which plan phases are active for this classification.
    # Optional so existing code that constructs CaseClassification without
    # this field continues to work (defaults to all phases active).
    active_phases: Optional[List[str]] = None
    # S3 addition: move_type derived from contract_type + country comparison.
    move_type: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────


def _normalize(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.strip().lower()


def _derive_move_type(
    contract_type: Optional[str],
    origin_country: Optional[str],
    destination_country: Optional[str],
) -> str:
    """
    Derive the coarse move_type from contract_type and the country pair.

    Priority order:
      1. contract_type = 'domestic_move'  → 'domestic'  (explicit user intent)
      2. contract_type = 'repatriation'   → 'return'
      3. Same origin and destination country → 'domestic'
      4. Anything else                    → 'international'
    """
    if contract_type == "domestic_move":
        return "domestic"
    if contract_type == "repatriation":
        return "return"
    if (
        origin_country
        and destination_country
        and _normalize(origin_country) == _normalize(destination_country)
    ):
        return "domestic"
    return "international"


def _active_phases_for(case_type: CaseType) -> List[str]:
    """Return the ordered list of plan phases active for this case type.

    Delegates to plan_scope so repatriation's additive ``return`` phase cannot
    drift from REPATRIATION_PHASES.
    """
    return active_phases_for_case_type(case_type)


def _normalize_employment_type(value: Optional[str]) -> Optional[str]:
    """Preserved for backward-compatibility — callers that pass employment_type still work."""
    return _normalize(value)


def classify_case(profile: dict, missing_fields: List[str]) -> CaseClassification:
    """
    Classify a relocation case given a profile dict and list of missing fields.

    S3 extension: if 'contract_type' is present in the profile it takes
    precedence over the legacy employment_type logic.  Existing callers that
    do not set contract_type continue to receive the original behaviour.
    """
    # ── S3: prefer explicit contract_type if available ────────────────────────
    contract_type: Optional[str] = _normalize(profile.get("contract_type"))
    origin_country: Optional[str] = profile.get("origin_country")
    destination_country: Optional[str] = profile.get("destination_country")
    move_date = profile.get("move_date")

    _legacy_risk_flags: List[str] = []

    if contract_type and contract_type not in {"unknown", None}:
        # ── New path: contract_type set by S3 intake questions ────────────────
        case_type: CaseType = contract_type  # type: ignore[assignment]
        move_type = _derive_move_type(contract_type, origin_country, destination_country)
        # No legacy risk flags on the new path; S3-specific flags are added below.
    else:
        # ── Legacy path: classify from employment_type (backward-compat) ─────
        employment_type = _normalize_employment_type(profile.get("employment_type"))
        works_remote = profile.get("works_remote")
        employer_country = profile.get("employer_country")

        if employment_type == "student":
            case_type = "student"
        elif employment_type in {"self_employed", "contractor", "freelancer"}:
            case_type = "self_employed"
        elif employment_type == "employee":
            case_type = "remote_worker" if works_remote is True else "employee_sponsored"
        else:
            case_type = "unknown"

        move_type = _derive_move_type(None, origin_country, destination_country)

        if (
            employment_type == "employee"
            and employer_country
            and destination_country
            and employer_country != destination_country
        ):
            _legacy_risk_flags.append("cross_border_payroll_risk")
        if works_remote is True:
            _legacy_risk_flags.append("remote_work_tax_residency_risk")

    # ── next_actions (shared logic) ───────────────────────────────────────────
    next_actions: List[NextAction] = []
    if not origin_country:
        next_actions.append(NextAction(
            key="collect_origin_country",
            label="Add your origin country",
            priority="high",
        ))
    if not destination_country:
        next_actions.append(NextAction(
            key="collect_destination_country",
            label="Add your destination country",
            priority="high",
        ))
    if not contract_type:
        next_actions.append(NextAction(
            key="collect_contract_type",
            label="Tell us what kind of move this is",
            priority="high",
        ))
    if not move_date:
        next_actions.append(NextAction(
            key="collect_move_date",
            label="Add your move date",
            priority="high",
        ))

    # ── blockers ──────────────────────────────────────────────────────────────
    blockers = [
        f for f in missing_fields
        if f in {"origin_country", "destination_country", "employment_type", "contract_type"}
    ]

    # ── risk_flags ────────────────────────────────────────────────────────────
    risk_flags: List[str] = list(_legacy_risk_flags)

    if move_type == "domestic":
        risk_flags.append("immigration_not_required")
    if case_type == "short_term_project":
        risk_flags.append("short_term_may_be_visa_free")
    if case_type in {"lta", "permanent_transfer", "employee_sponsored"}:
        if origin_country and destination_country:
            risk_flags.append("work_permit_required")
    if origin_country and destination_country and move_date:
        risk_flags.append("timeline_ready")
    else:
        risk_flags.append("timeline_missing_move_date")

    # ── active phases ─────────────────────────────────────────────────────────
    active_phases = _active_phases_for(case_type)

    return CaseClassification(
        case_type=case_type,
        risk_flags=risk_flags,
        blockers=blockers,
        next_actions=next_actions,
        active_phases=active_phases,
        move_type=move_type,
    )
