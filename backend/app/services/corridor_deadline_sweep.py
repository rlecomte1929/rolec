"""Corridor deadline-alert sweep — the daily job behind the alert ledger.

Resolves every open case through the EXISTING corridor engine and emits one
notification per (case, step, due-date) whose alert window contains today.

    POST /api/crons/corridor-deadline-sweep        {"dry_run": true}

Shape
-----
Two layers, split so the decision half needs no database:

* :func:`plan_case_alerts` — pure apart from reading the corridor YAML off disk.
  A case in, either a stated skip reason or a list of ``DueAlert`` out. This is
  what the boundary tests exercise.
* :func:`run_corridor_deadline_sweep` — the DB half: fetch cases, consult the
  ledger, write the outbox row and the ledger row in one transaction.

It never re-implements timeline logic. Dates come from
``relopass.corridors.scheduler`` — the same functions that date the step graph
everywhere else — because a second implementation is a second set of answers.

Never guess
-----------
A case with no corridor pathway, or no move date, is SKIPPED WITH A STATED
REASON and counted. It is not defaulted to today: an invented anchor produces
invented statutory deadlines, and an alert that is confidently wrong about a
legal window is worse than no alert. Every skip appears in the summary, so a
corridor that silently covers nothing is visible rather than merely quiet.

Known gap — completion state
----------------------------
Nothing in the product currently records "has THIS case completed THIS corridor
step". ``rce.steps`` is corridor-scoped and shared across cases, and
``case_requirement_checklist_state`` is keyed on ``requirement_items.id``, a
different taxonomy. So the sweep cannot suppress an alert for an obligation the
person has already discharged, and may remind someone about something they did.

``completed_step_ids`` is threaded through both layers so that becomes a
one-line change the day a completion source exists. Until then the honest
statement is: this alerts on schedule, not on progress.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Set

from sqlalchemy import bindparam, text as _sql_text

from ...relopass.corridors import load_corridor
from ...relopass.corridors.deadline_alerts import DueAlert, due_alerts, event_uid, render_alert
from ...relopass.corridors.scheduler import compute_deadlines, schedule_steps

log = logging.getLogger(__name__)

NOTIFICATION_TYPE = "corridor.deadline"

# Cases worth sweeping — in-flight ones whose deadlines can still be met.
_ACTIVE_PUBLIC_STATUSES = ("active", "on_hold", "draft")


@dataclass
class CaseSweepResult:
    """One case's outcome. Either ``skip_reason`` is set, or ``alerts`` is the
    (possibly empty) list of alerts whose window is open today."""

    case_ref: str
    corridor_id: Optional[str] = None
    skip_reason: Optional[str] = None
    alerts: List[DueAlert] = field(default_factory=list)


def _main_db():
    from ...database import db  # type: ignore[import]
    return db


def _engine():
    return _main_db().engine


def _t(name: str) -> str:
    """Schema-qualified on Postgres, bare on SQLite (matches milestone_reminders)."""
    try:
        dialect = _engine().dialect.name
    except Exception:
        dialect = "sqlite"
    return f"public.{name}" if dialect == "postgresql" else name


def _as_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Decision layer (no database)
# ─────────────────────────────────────────────────────────────────────────────


def plan_case_alerts(
    case: Dict[str, Any],
    *,
    today: date,
    completed_step_ids: Optional[Set[str]] = None,
) -> CaseSweepResult:
    """Which alerts are open for this case today, or why it was skipped.

    ``today`` is injected, never read from the clock, so the same case on the
    same day always plans the same alerts — which is what makes the sweep
    replayable and testable at a window boundary.
    """
    # Imported here: the resolver lives in a script module and pulls the
    # country-name → ISO-2 map with it. Duplicating that map is how a
    # name-spelled case ("NORWAY" rather than "NO") silently loses coverage.
    from ...scripts.populate_rce_from_cases import resolve_pathway_file

    case_ref = str(case.get("id"))
    path, corridor_id, _pathway_id = resolve_pathway_file(
        case.get("origin_country_code"), case.get("dest_country_code")
    )
    if path is None:
        return CaseSweepResult(
            case_ref=case_ref,
            corridor_id=corridor_id,
            skip_reason=f"no corridor pathway authored for {corridor_id or 'unknown corridor'}",
        )

    anchor = _as_date(case.get("target_move_date")) or _as_date(case.get("actual_move_date"))
    if anchor is None:
        # Deliberately NOT date.today(). See the module docstring.
        return CaseSweepResult(
            case_ref=case_ref,
            corridor_id=corridor_id,
            skip_reason="no target_move_date or actual_move_date on the case",
        )

    corridor = load_corridor(path)
    steps = corridor.step_graph
    schedule = schedule_steps(steps, anchor)
    deadlines = compute_deadlines(steps, anchor, schedule=schedule)
    alerts = due_alerts(
        steps,
        deadlines,
        today=today,
        completed_step_ids=completed_step_ids,
        destination=corridor.destination_country_iso3,
    )
    return CaseSweepResult(case_ref=case_ref, corridor_id=corridor_id, alerts=alerts)


# ─────────────────────────────────────────────────────────────────────────────
# Database layer
# ─────────────────────────────────────────────────────────────────────────────


def _fetch_open_cases() -> List[Dict[str, Any]]:
    sql = f"""
        SELECT c.id, c.origin_country_code, c.dest_country_code,
               c.target_move_date, c.actual_move_date, c.status,
               c.employee_id, c.hr_owner_id,
               pe.email AS employee_email,
               ph.email AS hr_email
        FROM {_t('cases')} c
        LEFT JOIN {_t('profiles')} pe ON pe.id = c.employee_id
        LEFT JOIN {_t('profiles')} ph ON ph.id = c.hr_owner_id
        WHERE lower(coalesce(c.status,'')) IN ('active', 'on_hold', 'draft')
        ORDER BY c.created_at
    """
    try:
        with _engine().connect() as conn:
            return [dict(r) for r in conn.execute(_sql_text(sql)).mappings().all()]
    except Exception as exc:  # noqa: BLE001
        log.error("corridor_deadline_sweep: case fetch failed: %s", exc)
        return []


def _already_fired(uids: Sequence[str]) -> Set[str]:
    """Which of these event_uids the ledger already holds.

    Checked in one query rather than per alert: the ledger is the exactly-once
    guard, and a per-alert round trip is how a slow sweep starts skipping work.
    """
    if not uids:
        return set()
    try:
        with _engine().connect() as conn:
            stmt = _sql_text(
                f"SELECT event_uid FROM {_t('corridor_deadline_events')} "
                "WHERE event_uid IN :uids"
            ).bindparams(bindparam("uids", expanding=True))
            rows = conn.execute(stmt, {"uids": list(uids)}).mappings().all()
        return {r["event_uid"] for r in rows}
    except Exception as exc:  # noqa: BLE001
        # Fail CLOSED: if we cannot prove an alert has not fired, do not fire it.
        # A missed reminder is recoverable; a duplicate one is spam that teaches
        # the reader to ignore the next.
        log.error("corridor_deadline_sweep: ledger read failed, suppressing: %s", exc)
        return set(uids)


def _resolve_recipient(case: Dict[str, Any], alert: DueAlert) -> Optional[Dict[str, str]]:
    """Who this alert goes to. Fail-soft: None is recorded as 'no_contact'."""
    party = (alert.responsible_party or "").upper()
    if party in ("EMPLOYER", "HR", "EMPLOYER_HR") and case.get("hr_email"):
        return {"user_id": str(case.get("hr_owner_id")), "email": str(case["hr_email"])}
    if case.get("employee_email"):
        return {"user_id": str(case.get("employee_id")), "email": str(case["employee_email"])}
    if case.get("hr_email"):
        return {"user_id": str(case.get("hr_owner_id")), "email": str(case["hr_email"])}
    return None


def _ledger_row(
    conn,
    *,
    uid: str,
    case_ref: str,
    corridor_id: str,
    alert: DueAlert,
    today: date,
    status: str,
    recipient: Optional[str],
    detail: Optional[str],
) -> None:
    is_pg = _engine().dialect.name == "postgresql"
    conn.execute(
        _sql_text(
            f"INSERT INTO {_t('corridor_deadline_events')} "
            "(event_uid, case_ref, corridor_id, step_id, tag_name, jurisdiction, "
            " due_date, trigger_date, lead_days, fired_on, status, channel, recipient, detail) "
            "VALUES (:uid, :case_ref, :corridor_id, :step_id, :tag, :juris, "
            " :due, :trigger, :lead, :fired_on, :status, :channel, :recipient, :detail)"
            + (" ON CONFLICT (event_uid) DO NOTHING" if is_pg else "")
        ),
        {
            "uid": uid,
            "case_ref": case_ref,
            "corridor_id": corridor_id,
            "step_id": alert.step_id,
            "tag": alert.tag,
            "juris": alert.jurisdiction,
            "due": alert.due_date.isoformat(),
            "trigger": alert.trigger_date.isoformat(),
            "lead": alert.lead_days,
            "fired_on": today.isoformat(),
            "status": status,
            "channel": alert.channel,
            "recipient": recipient,
            "detail": detail,
        },
    )


def _emit(
    case: Dict[str, Any],
    result: CaseSweepResult,
    alert: DueAlert,
    uid: str,
    today: date,
) -> str:
    """Send one alert and record it. Returns the ledger status written.

    Outbox row and ledger row go in ONE transaction, so the ledger can never
    claim an alert was sent that was not queued. The reverse — a crash after
    commit but before dispatch — is the at-least-once edge the brief names, and
    the copy is safe to repeat.
    """
    recipient = _resolve_recipient(case, alert)
    corridor_id = result.corridor_id or ""

    if recipient is None:
        try:
            with _engine().begin() as conn:
                _ledger_row(
                    conn, uid=uid, case_ref=result.case_ref, corridor_id=corridor_id,
                    alert=alert, today=today, status="no_contact", recipient=None,
                    detail="no employee or HR email resolvable for this case",
                )
        except Exception as exc:  # noqa: BLE001
            log.error("corridor_deadline_sweep: no_contact ledger write failed %s: %s", uid, exc)
        return "no_contact"

    copy = render_alert(alert)
    payload = {
        "case_id": result.case_ref,
        "corridor_id": corridor_id,
        "step_id": alert.step_id,
        "tag": alert.tag,
        "due_date": alert.due_date.isoformat(),
        "trigger_date": alert.trigger_date.isoformat(),
        "days_remaining": alert.days_remaining,
        "idempotency_key": uid,
        "subject": copy["subject"],
        "body": copy["body"],
    }
    is_pg = _engine().dialect.name == "postgresql"
    try:
        with _engine().begin() as conn:
            conn.execute(
                _sql_text(
                    f"INSERT INTO {_t('notification_outbox')} "
                    "(id, notification_id, user_id, to_email, type, payload, status) "
                    "VALUES (:id, NULL, :uid, :email, :type, "
                    + ("CAST(:payload AS jsonb)" if is_pg else ":payload")
                    + ", 'pending')"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "uid": recipient["user_id"],
                    "email": recipient["email"],
                    "type": NOTIFICATION_TYPE,
                    "payload": json.dumps(payload),
                },
            )
            _ledger_row(
                conn, uid=uid, case_ref=result.case_ref, corridor_id=corridor_id,
                alert=alert, today=today, status="fired",
                recipient=recipient["email"], detail=None,
            )
        return "fired"
    except Exception as exc:  # noqa: BLE001
        log.error("corridor_deadline_sweep: emit failed %s: %s", uid, exc)
        # Record the failure so an operator sees it. Best-effort: if this write
        # fails too, the log line above is the only trace, which is why the
        # summary also counts errors.
        try:
            with _engine().begin() as conn:
                _ledger_row(
                    conn, uid=uid, case_ref=result.case_ref, corridor_id=corridor_id,
                    alert=alert, today=today, status="error",
                    recipient=recipient["email"], detail=str(exc)[:500],
                )
        except Exception:  # noqa: BLE001
            pass
        return "error"


def run_corridor_deadline_sweep(
    *,
    today: Optional[date] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Sweep every open case. Returns a summary an operator can read.

    ``dry_run=True`` plans everything and writes nothing — the report answers
    "what would fire today, and what was skipped and why".
    """
    today = today or datetime.now(timezone.utc).date()
    cases = _fetch_open_cases()

    results: List[CaseSweepResult] = []
    for case in cases:
        try:
            results.append(plan_case_alerts(case, today=today))
        except Exception as exc:  # noqa: BLE001
            log.error("corridor_deadline_sweep: plan failed for case %s: %s", case.get("id"), exc)
            results.append(
                CaseSweepResult(case_ref=str(case.get("id")), skip_reason=f"planning error: {exc}")
            )

    skipped = [r for r in results if r.skip_reason]
    planned = [(r, a) for r in results if not r.skip_reason for a in r.alerts]

    uids = [event_uid(r.case_ref, a.step_id, a.due_date) for r, a in planned]
    already = set() if dry_run else _already_fired(uids)

    pending = [(r, a, u) for (r, a), u in zip(planned, uids) if u not in already]

    summary: Dict[str, Any] = {
        "today": today.isoformat(),
        "dry_run": dry_run,
        "cases_scanned": len(cases),
        "cases_skipped": len(skipped),
        "alerts_in_window": len(planned),
        "already_fired": len(already),
        "fired": 0,
        "no_contact": 0,
        "errors": 0,
        # Every skip named, so a corridor that covers nothing is visible.
        "skips": [
            {"case_ref": r.case_ref, "corridor_id": r.corridor_id, "reason": r.skip_reason}
            for r in skipped
        ],
        "would_fire" if dry_run else "sent": [],
    }

    by_case = {r.case_ref: c for r, c in zip(results, cases) if not r.skip_reason}
    key = "would_fire" if dry_run else "sent"

    for result, alert, uid in pending:
        entry = {
            "case_ref": result.case_ref,
            "corridor_id": result.corridor_id,
            "step_id": alert.step_id,
            "tag": alert.tag,
            "due_date": alert.due_date.isoformat(),
            "days_remaining": alert.days_remaining,
            "event_uid": uid,
        }
        if dry_run:
            entry["subject"] = render_alert(alert)["subject"]
            summary[key].append(entry)
            continue

        status = _emit(by_case.get(result.case_ref, {}), result, alert, uid, today)
        entry["status"] = status
        summary[key].append(entry)
        if status == "fired":
            summary["fired"] += 1
        elif status == "no_contact":
            summary["no_contact"] += 1
        else:
            summary["errors"] += 1

    log.info(
        "corridor_deadline_sweep: today=%s dry_run=%s cases=%d skipped=%d "
        "in_window=%d already=%d fired=%d no_contact=%d errors=%d",
        today, dry_run, len(cases), len(skipped), len(planned),
        len(already), summary["fired"], summary["no_contact"], summary["errors"],
    )
    return summary
