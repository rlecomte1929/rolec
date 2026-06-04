"""
Compliance Alerts API — BL-Compliance.4 (AIQ-746).

GET   /api/compliance/alerts            — open compliance alerts for the HR's
                                          company, ordered by severity.
POST  /api/compliance/evaluate          — run the rule evaluator for the HR's
                                          company (fires new alerts on demand).
POST  /api/compliance/evaluate-all      — admin-only fleet-wide run; dry-run
                                          by default. Designed for the daily
                                          scheduled cron.
PATCH /api/compliance/alerts/{alert_id} — resolve / dismiss an alert.

HR endpoints are tenant-scoped to the caller's company via the parent
relocation_case. The admin endpoint is fleet-wide.
"""
import logging
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_org_id_for_hr_user, require_admin
from ..db import SessionLocal
from ..services.compliance_evaluator import run_compliance_evaluation

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compliance", tags=["compliance"])

# critical → high → medium → low
_SEVERITY_RANK = (
    "case r.severity when 'critical' then 0 when 'high' then 1 "
    "when 'medium' then 2 else 3 end"
)

_LIST_SQL = text(
    f"""
    select a.id::text       as id,
           a.case_id::text  as case_id,
           a.status         as status,
           a.detail         as detail,
           a.fired_at       as fired_at,
           r.id::text       as rule_id,
           r.category       as category,
           r.severity       as severity,
           r.description    as description,
           rc.employee_id   as employee_id,
           rc.host_country  as host_country,
           rc.home_country  as home_country
    from public.compliance_alerts a
    join public.compliance_rules r on r.id = a.rule_id
    join public.relocation_cases rc on rc.id = a.case_id
    where rc.company_id = :company_id
      and a.status = 'open'
    order by {_SEVERITY_RANK}, a.fired_at desc
    """
)

# UPDATE ... FROM relocation_cases enforces the tenant boundary: an alert is only
# updatable when its parent case belongs to the caller's company.
_UPDATE_SQL = text(
    """
    update public.compliance_alerts a
       set status = :status,
           resolved_at = now()
      from public.relocation_cases rc
     where a.id = :alert_id
       and rc.id = a.case_id
       and rc.company_id = :company_id
       and a.status = 'open'
    returning a.id
    """
)


class ComplianceAlert(BaseModel):
    id: str
    case_id: str
    status: str
    severity: str
    category: str
    description: Optional[str] = None
    detail: Dict[str, Any] = {}
    fired_at: Optional[str] = None
    employee_id: Optional[str] = None
    host_country: Optional[str] = None
    home_country: Optional[str] = None


class AlertsResponse(BaseModel):
    alerts: List[ComplianceAlert]
    counts_by_severity: Dict[str, int]


class EvaluateResponse(BaseModel):
    cases_evaluated: int
    alerts_created: int
    alerts_skipped_existing: int


class UpdateAlertBody(BaseModel):
    status: Literal["resolved", "dismissed"]


@router.get("/alerts", response_model=AlertsResponse)
def list_alerts(company_id: str = Depends(get_org_id_for_hr_user)) -> AlertsResponse:
    if not company_id:
        return AlertsResponse(alerts=[], counts_by_severity={})
    with SessionLocal() as db:
        rows = db.execute(_LIST_SQL, {"company_id": company_id}).mappings().all()
    alerts: List[ComplianceAlert] = []
    counts: Dict[str, int] = {}
    for r in rows:
        alerts.append(
            ComplianceAlert(
                id=r["id"],
                case_id=r["case_id"],
                status=r["status"],
                severity=r["severity"],
                category=r["category"],
                description=r["description"],
                detail=r["detail"] if isinstance(r["detail"], dict) else {},
                fired_at=r["fired_at"].isoformat() if r["fired_at"] else None,
                employee_id=str(r["employee_id"]) if r["employee_id"] is not None else None,
                host_country=r["host_country"],
                home_country=r["home_country"],
            )
        )
        counts[r["severity"]] = counts.get(r["severity"], 0) + 1
    return AlertsResponse(alerts=alerts, counts_by_severity=counts)


@router.post("/evaluate", response_model=EvaluateResponse)
def evaluate_company(company_id: str = Depends(get_org_id_for_hr_user)) -> EvaluateResponse:
    if not company_id:
        raise HTTPException(status_code=400, detail="No company for current user")
    with SessionLocal() as db:
        result = run_compliance_evaluation(db, company_id=company_id)
        db.commit()
    return EvaluateResponse(
        cases_evaluated=result.cases_evaluated,
        alerts_created=result.alerts_created,
        alerts_skipped_existing=result.alerts_skipped_existing,
    )


class EvaluateAllResponse(BaseModel):
    cases_evaluated: int
    alerts_created: int
    alerts_skipped_existing: int
    dry_run: bool


@router.post("/evaluate-all", response_model=EvaluateAllResponse)
def evaluate_all(
    dry_run: bool = Query(True),
    _admin: Dict[str, Any] = Depends(require_admin),
) -> EvaluateAllResponse:
    """Fleet-wide compliance run (admin-only). Defaults to dry_run=True so the
    scheduled cron is safe-by-default; pass dry_run=false explicitly to persist."""
    with SessionLocal() as db:
        result = run_compliance_evaluation(db, dry_run=dry_run)
        if not dry_run:
            db.commit()
        else:
            db.rollback()
    return EvaluateAllResponse(
        cases_evaluated=result.cases_evaluated,
        alerts_created=result.alerts_created,
        alerts_skipped_existing=result.alerts_skipped_existing,
        dry_run=dry_run,
    )


@router.patch("/alerts/{alert_id}")
def update_alert(
    alert_id: str,
    body: UpdateAlertBody,
    company_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, str]:
    with SessionLocal() as db:
        row = db.execute(
            _UPDATE_SQL,
            {"status": body.status, "alert_id": alert_id, "company_id": company_id},
        ).first()
        db.commit()
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found or not open")
    return {"id": alert_id, "status": body.status}
