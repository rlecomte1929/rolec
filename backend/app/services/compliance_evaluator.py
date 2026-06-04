"""BL-Compliance.3 (AIQ-745) — compliance rule evaluator.

Walks open cases, evaluates each active ``compliance_rules`` row's
``trigger_condition`` against the case's data, and inserts a
``compliance_alerts`` row when a rule fires — deduped so there is at most one
*open* alert per (case, rule).

Design: the firing logic (:func:`evaluate`) is a pure function over plain
dataclasses, so the rules can be unit-tested without a database. All DB I/O
lives behind the :class:`ComplianceDataSource` / :class:`AlertStore` Protocols;
:class:`SqlComplianceDataSource` / :class:`SqlAlertStore` are the SQLAlchemy
implementations used in production.

``trigger_condition`` contract (seeded by BL-Compliance.2)::

    {
      "type":     "date_threshold" | "day_count" | "missing_field",
      "field":    "<resolved case field>",
      "operator": "within_days" | "gte" | "lte" | "is_null",
      "value":    <number | null>,
      "unit":     "days"          # for date_threshold / day_count
    }

Field resolution (over the populated ``relocation_cases`` system)::

    permit_expiry_date       <- immigration_cases.permit_expiry_date
    employer_registration_id <- imm_employee_profiles.employer_reg_number
    days_present_in_host      <- today - relocation_cases.expected_start_date  (v1 proxy)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Optional, Protocol, Sequence

from sqlalchemy import text

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Plain data the pure logic operates on
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ComplianceRule:
    id: str
    category: str
    severity: str
    trigger_condition: dict
    active: bool = True


@dataclass(frozen=True)
class CaseComplianceData:
    """Resolved per-case field values the rules evaluate against."""

    case_id: str
    permit_expiry_date: Optional[date] = None
    employer_registration_id: Optional[str] = None
    days_present_in_host: Optional[int] = None

    def get(self, field_name: str) -> Any:
        return getattr(self, field_name, None)


@dataclass(frozen=True)
class RuleFiring:
    case_id: str
    rule_id: str
    detail: dict


# ─────────────────────────────────────────────────────────────────────────────
# Pure firing logic — no DB, fully unit-testable
# ─────────────────────────────────────────────────────────────────────────────


def _evaluate_condition(
    cond: dict, case: CaseComplianceData, today: date
) -> Optional[dict]:
    """Return a ``detail`` dict if the rule fires for this case, else ``None``."""
    ctype = cond.get("type")
    field_name = cond.get("field")
    operator = cond.get("operator")
    value = cond.get("value")
    actual = case.get(field_name)

    if ctype == "missing_field":
        if actual is None or (isinstance(actual, str) and actual.strip() == ""):
            return {"field": field_name, "reason": "missing"}
        return None

    if ctype == "date_threshold":
        if actual is None or value is None:
            return None  # field unresolved -> cannot evaluate -> no fire
        days_until = (actual - today).days
        if operator == "within_days" and 0 <= days_until <= int(value):
            return {"field": field_name, "days_until": days_until, "threshold": int(value)}
        return None

    if ctype == "day_count":
        if actual is None or value is None:
            return None
        count = int(actual)
        if operator == "gte" and count >= int(value):
            return {"field": field_name, "count": count, "threshold": int(value)}
        if operator == "lte" and count <= int(value):
            return {"field": field_name, "count": count, "threshold": int(value)}
        return None

    log.warning("compliance_evaluator: unknown condition type %r — rule skipped", ctype)
    return None


def evaluate(
    rules: Sequence[ComplianceRule],
    case: CaseComplianceData,
    today: Optional[date] = None,
) -> list[RuleFiring]:
    """Which active rules fire for this case. Pure; ``today`` is injectable."""
    today = today or date.today()
    firings: list[RuleFiring] = []
    for rule in rules:
        if not rule.active:
            continue
        detail = _evaluate_condition(rule.trigger_condition, case, today)
        if detail is not None:
            firings.append(RuleFiring(case_id=case.case_id, rule_id=rule.id, detail=detail))
    return firings


# ─────────────────────────────────────────────────────────────────────────────
# I/O seams
# ─────────────────────────────────────────────────────────────────────────────


class ComplianceDataSource(Protocol):
    def active_rules(self) -> Sequence[ComplianceRule]: ...
    def open_cases(self) -> Iterable[CaseComplianceData]: ...


class AlertStore(Protocol):
    def open_alert_exists(self, case_id: str, rule_id: str) -> bool: ...
    def insert_alert(self, firing: RuleFiring, severity: str) -> None: ...


@dataclass
class EvaluationResult:
    cases_evaluated: int = 0
    alerts_created: int = 0
    alerts_skipped_existing: int = 0


def run_evaluation(
    source: ComplianceDataSource,
    store: AlertStore,
    today: Optional[date] = None,
) -> EvaluationResult:
    """Evaluate every active rule against every open case; persist new alerts.

    Deduped: an existing *open* alert for the same (case, rule) is not
    re-created.
    """
    today = today or date.today()
    rules = list(source.active_rules())
    rule_by_id = {r.id: r for r in rules}
    result = EvaluationResult()
    for case in source.open_cases():
        result.cases_evaluated += 1
        for firing in evaluate(rules, case, today):
            if store.open_alert_exists(firing.case_id, firing.rule_id):
                result.alerts_skipped_existing += 1
                continue
            store.insert_alert(firing, rule_by_id[firing.rule_id].severity)
            result.alerts_created += 1
    log.info(
        "compliance_evaluator: %d cases, %d alerts created, %d skipped (existing)",
        result.cases_evaluated,
        result.alerts_created,
        result.alerts_skipped_existing,
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# SQLAlchemy-backed implementations (production wiring)
# ─────────────────────────────────────────────────────────────────────────────

# Open = not archived. relocation_cases is the populated case system; the
# immigration data (permit_expiry) keys to it via immigration_cases.case_id.
def _open_cases_sql(company_scoped: bool):
    where = "where rc.archived_at is null"
    if company_scoped:
        where += " and rc.company_id = :company_id"
    return text(
        f"""
        select
            rc.id::text              as case_id,
            ic.permit_expiry_date    as permit_expiry_date,
            prof.employer_reg_number as employer_registration_id,
            rc.expected_start_date   as expected_start_date
        from public.relocation_cases rc
        left join lateral (
            select permit_expiry_date
            from public.immigration_cases i
            where i.case_id = rc.id
            order by i.created_at desc
            limit 1
        ) ic on true
        left join lateral (
            -- imm_employee_profiles.case_id is text; relocation_cases.id is uuid.
            select employer_reg_number
            from public.imm_employee_profiles p
            where p.case_id = rc.id::text
            order by p.created_at desc
            limit 1
        ) prof on true
        {where}
        """
    )

_ACTIVE_RULES_SQL = text(
    "select id::text, category, severity, trigger_condition, active "
    "from public.compliance_rules where active = true"
)

_ALERT_EXISTS_SQL = text(
    "select 1 from public.compliance_alerts "
    "where case_id = :case_id and rule_id = :rule_id and status = 'open' limit 1"
)

_INSERT_ALERT_SQL = text(
    "insert into public.compliance_alerts (case_id, rule_id, status, detail) "
    "values (:case_id, :rule_id, 'open', cast(:detail as jsonb))"
)


class SqlComplianceDataSource:
    """Reads rules + open cases from the DB via a SQLAlchemy session."""

    def __init__(
        self, db: Any, today: Optional[date] = None, company_id: Optional[str] = None
    ) -> None:
        self._db = db
        self._today = today or date.today()
        self._company_id = company_id

    def active_rules(self) -> Sequence[ComplianceRule]:
        rows = self._db.execute(_ACTIVE_RULES_SQL).mappings().all()
        return [
            ComplianceRule(
                id=r["id"],
                category=r["category"],
                severity=r["severity"],
                trigger_condition=(
                    r["trigger_condition"]
                    if isinstance(r["trigger_condition"], dict)
                    else json.loads(r["trigger_condition"] or "{}")
                ),
                active=bool(r["active"]),
            )
            for r in rows
        ]

    def open_cases(self) -> Iterable[CaseComplianceData]:
        sql = _open_cases_sql(self._company_id is not None)
        params = {"company_id": self._company_id} if self._company_id is not None else {}
        rows = self._db.execute(sql, params).mappings().all()
        for r in rows:
            start = r["expected_start_date"]
            days_present = (self._today - start).days if start is not None else None
            yield CaseComplianceData(
                case_id=r["case_id"],
                permit_expiry_date=r["permit_expiry_date"],
                employer_registration_id=r["employer_registration_id"],
                days_present_in_host=days_present,
            )


class SqlAlertStore:
    """Persists alerts via a SQLAlchemy session (caller commits)."""

    def __init__(self, db: Any) -> None:
        self._db = db

    def open_alert_exists(self, case_id: str, rule_id: str) -> bool:
        row = self._db.execute(
            _ALERT_EXISTS_SQL, {"case_id": case_id, "rule_id": rule_id}
        ).first()
        return row is not None

    def insert_alert(self, firing: RuleFiring, severity: str) -> None:
        detail = dict(firing.detail)
        detail.setdefault("severity", severity)
        self._db.execute(
            _INSERT_ALERT_SQL,
            {
                "case_id": firing.case_id,
                "rule_id": firing.rule_id,
                "detail": json.dumps(detail),
            },
        )


def run_compliance_evaluation(
    db: Any, today: Optional[date] = None, company_id: Optional[str] = None
) -> EvaluationResult:
    """Production entry point: evaluate open cases and persist new alerts.

    Pass ``company_id`` to scope the run to one company's open cases (used by the
    HR-triggered endpoint to avoid a full-fleet run). The caller owns the
    transaction — commit after this returns.
    """
    source = SqlComplianceDataSource(db, today=today, company_id=company_id)
    store = SqlAlertStore(db)
    return run_evaluation(source, store, today=today)
