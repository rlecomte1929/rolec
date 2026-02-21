from typing import List, Literal, Optional

from pydantic import BaseModel


CaseType = Literal[
    "employee_sponsored",
    "remote_worker",
    "student",
    "self_employed",
    "unknown",
]
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


def _normalize_employment_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.strip().lower()


def classify_case(profile: dict, missing_fields: List[str]) -> CaseClassification:
    employment_type = _normalize_employment_type(profile.get("employment_type"))
    works_remote = profile.get("works_remote")
    origin_country = profile.get("origin_country")
    destination_country = profile.get("destination_country")
    employer_country = profile.get("employer_country")
    move_date = profile.get("move_date")

    if employment_type == "student":
        case_type: CaseType = "student"
    elif employment_type in {"self_employed", "contractor", "freelancer"}:
        case_type = "self_employed"
    elif employment_type == "employee":
        case_type = "remote_worker" if works_remote is True else "employee_sponsored"
    else:
        case_type = "unknown"

    next_actions: List[NextAction] = []
    if not origin_country:
        next_actions.append(
            NextAction(
                key="collect_origin_country",
                label="Add your origin country",
                priority="high",
            )
        )
    if not destination_country:
        next_actions.append(
            NextAction(
                key="collect_destination_country",
                label="Add your destination country",
                priority="high",
            )
        )
    if not employment_type:
        next_actions.append(
            NextAction(
                key="collect_employment_type",
                label="Add your employment type",
                priority="high",
            )
        )
    if not move_date:
        next_actions.append(
            NextAction(
                key="collect_move_date",
                label="Add your move date",
                priority="high",
            )
        )
    if employment_type == "employee" and not employer_country:
        next_actions.append(
            NextAction(
                key="collect_employer_country",
                label="Add your employer country",
                priority="medium",
            )
        )
    if employment_type == "employee" and works_remote is None:
        next_actions.append(
            NextAction(
                key="confirm_remote_work",
                label="Confirm whether you will work remotely",
                priority="medium",
            )
        )

    blockers = [
        field
        for field in missing_fields
        if field in {"origin_country", "destination_country", "employment_type"}
    ]

    risk_flags: List[str] = []
    if (
        employment_type == "employee"
        and employer_country
        and destination_country
        and employer_country != destination_country
    ):
        risk_flags.append("cross_border_payroll_risk")
    if works_remote is True:
        risk_flags.append("remote_work_tax_residency_risk")
    if origin_country and destination_country and origin_country == destination_country:
        risk_flags.append("same_country_move")
    if origin_country and destination_country and move_date:
        risk_flags.append("timeline_ready")
    else:
        risk_flags.append("timeline_missing_move_date")

    return CaseClassification(
        case_type=case_type,
        risk_flags=risk_flags,
        blockers=blockers,
        next_actions=next_actions,
    )
