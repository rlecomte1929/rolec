"""HR duty-of-care board — company-scoped aggregation + a pure R/A/G classifier.

Read-only. No LLM. No new tables. Untracked signals serialize as ``not_tracked``
and are never classified green (AIQ-1527 / AIQ-2087 honesty rule).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Mapping, Optional, Sequence

from sqlalchemy import text

RED = "red"
AMBER = "amber"
GREEN = "green"
UNKNOWN = "unknown"
NOT_TRACKED = "not_tracked"

_UNTRACKED = frozenset({UNKNOWN, NOT_TRACKED})

_BOARD_SQL = text(
    """
    SELECT
        rc.id                    AS case_id,
        rc.company_id            AS company_id,
        rc.employee_id           AS employee_id,
        rc.host_country          AS host_country,
        rc.home_country           AS home_country,
        rc.expected_start_date    AS expected_start_date,
        rc.status                AS status,
        ic.permit_expiry_date     AS permit_expiry_date,
        ic.permit_type            AS permit_type,
        ic.status                AS permit_status,
        CASE WHEN ic.case_id IS NULL THEN 0 ELSE 1 END AS has_immigration_row,
        COALESCE(al.has_critical, 0) AS has_critical_alert,
        COALESCE(ck.item_count, 0) AS checklist_item_count,
        COALESCE(ck.completed_count, 0) AS checklist_completed_count
    FROM relocation_cases rc
    LEFT JOIN immigration_cases ic ON ic.case_id = rc.id
    LEFT JOIN (
        SELECT a.case_id AS case_id,
               MAX(CASE WHEN r.severity = 'critical' THEN 1 ELSE 0 END)
                   AS has_critical
          FROM compliance_alerts a
          JOIN compliance_rules r ON r.id = a.rule_id
         WHERE a.status = 'open'
         GROUP BY a.case_id
    ) al ON al.case_id = rc.id
    LEFT JOIN (
        SELECT case_id,
               COUNT(*) AS item_count,
               SUM(CASE WHEN completed THEN 1 ELSE 0 END) AS completed_count
          FROM case_requirement_checklist_state
         GROUP BY case_id
    ) ck ON ck.case_id = rc.id
    WHERE rc.company_id = :company_id
      AND (rc.archived_at IS NULL)
      AND (rc.status IS NULL OR rc.status NOT IN ('closed', 'rejected'))
    """
)


def _as_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        return date.fromisoformat(value.strip()[:10])
    return None


def _as_bool(value: Any) -> bool:
    return bool(value) and value not in (0, "0", "false", "False")


def classify_permit(
    *,
    has_immigration_row: bool,
    permit_expiry: Optional[date],
    today: date,
) -> str:
    """Permit cell. A missing immigration_cases row is unknown, never green."""
    if not has_immigration_row:
        return UNKNOWN
    if permit_expiry is None:
        return UNKNOWN
    days = (permit_expiry - today).days
    if days < 0 or days <= 30:
        return RED
    if days <= 60:
        return AMBER
    return GREEN


def classify_checklist(*, item_count: int, completed_count: int) -> str:
    """Checklist cell. Zero stored rows → unknown (not an all-clear)."""
    if item_count <= 0:
        return UNKNOWN
    if completed_count < item_count:
        return AMBER
    return GREEN


def classify_alert(*, has_critical_alert: bool) -> str:
    return RED if has_critical_alert else GREEN


def overall_rating(
    *,
    permit: str,
    alert: str,
    checklist: str,
    a1: str = NOT_TRACKED,
    medical: str = NOT_TRACKED,
    insurance: str = NOT_TRACKED,
) -> str:
    """Row rating. Untracked cells never count as green and never make the row green
    on their own. A missing permit (core signal) blocks an all-clear."""
    cells = (permit, alert, checklist, a1, medical, insurance)
    if RED in cells:
        return RED
    if AMBER in cells:
        return AMBER
    if permit in _UNTRACKED:
        return UNKNOWN
    tracked = [c for c in cells if c not in _UNTRACKED]
    if not tracked:
        return UNKNOWN
    return GREEN


@dataclass(frozen=True)
class DutyOfCareSignals:
    permit: str
    permit_expiry: Optional[date]
    permit_type: Optional[str]
    alert: str
    checklist: str
    checklist_completed: int
    checklist_total: int
    a1: str
    medical: str
    insurance: str
    overall: str
    departing_soon: bool


def classify_row(
    *,
    has_immigration_row: bool,
    permit_expiry: Optional[date],
    permit_type: Optional[str],
    has_critical_alert: bool,
    checklist_item_count: int,
    checklist_completed_count: int,
    expected_start: Optional[date],
    today: date,
    a1: str = NOT_TRACKED,
    medical: str = NOT_TRACKED,
    insurance: str = NOT_TRACKED,
) -> DutyOfCareSignals:
    permit = classify_permit(
        has_immigration_row=has_immigration_row,
        permit_expiry=permit_expiry,
        today=today,
    )
    alert = classify_alert(has_critical_alert=has_critical_alert)
    checklist = classify_checklist(
        item_count=checklist_item_count,
        completed_count=checklist_completed_count,
    )
    departing = False
    if expected_start is not None:
        days = (expected_start - today).days
        departing = 0 <= days <= 30
    overall = overall_rating(
        permit=permit,
        alert=alert,
        checklist=checklist,
        a1=a1,
        medical=medical,
        insurance=insurance,
    )
    return DutyOfCareSignals(
        permit=permit,
        permit_expiry=permit_expiry,
        permit_type=permit_type,
        alert=alert,
        checklist=checklist,
        checklist_completed=checklist_completed_count,
        checklist_total=checklist_item_count,
        a1=a1,
        medical=medical,
        insurance=insurance,
        overall=overall,
        departing_soon=departing,
    )


def row_to_payload(
    case_id: str,
    company_id: str,
    employee_id: Optional[str],
    host_country: Optional[str],
    home_country: Optional[str],
    expected_start: Optional[date],
    signals: DutyOfCareSignals,
) -> dict[str, Any]:
    return {
        "case_id": str(case_id),
        "company_id": str(company_id) if company_id is not None else None,
        "employee_id": str(employee_id) if employee_id is not None else None,
        "host_country": host_country,
        "home_country": home_country,
        "expected_start_date": expected_start.isoformat() if expected_start else None,
        "departing_soon": signals.departing_soon,
        "overall": signals.overall,
        "permit": {
            "status": signals.permit,
            "expiry_date": (
                signals.permit_expiry.isoformat() if signals.permit_expiry else None
            ),
            "type": signals.permit_type,
        },
        "alert": {"status": signals.alert},
        "checklist": {
            "status": signals.checklist,
            "completed": signals.checklist_completed,
            "total": signals.checklist_total,
        },
        "a1": {"status": signals.a1},
        "medical": {"status": signals.medical},
        "insurance": {"status": signals.insurance},
    }


def classify_db_row(raw: Mapping[str, Any], today: date) -> dict[str, Any]:
    signals = classify_row(
        has_immigration_row=_as_bool(raw.get("has_immigration_row")),
        permit_expiry=_as_date(raw.get("permit_expiry_date")),
        permit_type=raw.get("permit_type"),
        has_critical_alert=_as_bool(raw.get("has_critical_alert")),
        checklist_item_count=int(raw.get("checklist_item_count") or 0),
        checklist_completed_count=int(raw.get("checklist_completed_count") or 0),
        expected_start=_as_date(raw.get("expected_start_date")),
        today=today,
    )
    return row_to_payload(
        case_id=str(raw["case_id"]),
        company_id=str(raw.get("company_id") or ""),
        employee_id=raw.get("employee_id"),
        host_country=raw.get("host_country"),
        home_country=raw.get("home_country"),
        expected_start=_as_date(raw.get("expected_start_date")),
        signals=signals,
    )


def list_duty_of_care_board(
    db: Any,
    company_id: str,
    *,
    today: Optional[date] = None,
) -> list[dict[str, Any]]:
    """One roll-up row per active case for ``company_id``. Empty company → []."""
    if not company_id:
        return []
    today = today or date.today()
    rows: Sequence[Mapping[str, Any]] = db.execute(
        _BOARD_SQL, {"company_id": company_id}
    ).mappings().all()
    return [classify_db_row(r, today) for r in rows]


def case_ids(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    return {str(r["case_id"]) for r in rows}
