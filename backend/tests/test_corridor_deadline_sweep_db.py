"""End-to-end sweep against a real (SQLite) database.

Covers the half that plan_case_alerts cannot: that the SQL is well-formed, that
dry-run writes nothing, that a real run writes BOTH the outbox row and the ledger
row, and that a second run on the same day fires nothing.

Defence in depth, verified by sabotage: with the ledger pre-check disabled, only
`test_a_second_run_the_same_day_fires_nothing` fails — the whole-window test still
passes. That is not luck. The outbox row and the ledger row commit in ONE
transaction, so the ledger's primary key rejects the duplicate and takes the
outbox insert down with it. A duplicate email is therefore structurally
impossible even if the pre-check is wrong; the pre-check exists to avoid the
error path, not to be the only guard.

CAVEAT, stated because a green SQLite run is easy to over-read: SQLite does not
exercise the Postgres CHECK on `status`, the ON CONFLICT clause, or jsonb
casting. What it does prove is that the statements parse, bind, and transact, and
that the exactly-once logic is right. The Postgres-specific guarantees are
enforced by the migration itself.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from backend.app.services import corridor_deadline_sweep as sweep

MOVE = date(2026, 3, 1)
DUE = date(2026, 5, 31)          # (MOVE + 1 day travel) + FR_NO's 90-day window
OPENS = DUE - timedelta(days=30)

_SCHEMA = [
    """CREATE TABLE cases (
        id TEXT PRIMARY KEY, origin_country_code TEXT, dest_country_code TEXT,
        target_move_date DATE, actual_move_date DATE, status TEXT,
        employee_id TEXT, hr_owner_id TEXT, created_at TEXT)""",
    """CREATE TABLE profiles (id TEXT PRIMARY KEY, email TEXT)""",
    """CREATE TABLE notification_outbox (
        id TEXT PRIMARY KEY, notification_id TEXT, user_id TEXT, to_email TEXT,
        type TEXT, payload TEXT, status TEXT, last_error TEXT, sent_at TEXT)""",
    """CREATE TABLE corridor_deadline_events (
        event_uid TEXT PRIMARY KEY, case_ref TEXT NOT NULL, corridor_id TEXT NOT NULL,
        step_id TEXT NOT NULL, tag_name TEXT NOT NULL, jurisdiction TEXT,
        due_date DATE NOT NULL, trigger_date DATE NOT NULL, lead_days INTEGER NOT NULL,
        fired_on DATE NOT NULL, status TEXT NOT NULL, channel TEXT NOT NULL,
        recipient TEXT, detail TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""",
]


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        for ddl in _SCHEMA:
            conn.execute(text(ddl))
        conn.execute(text(
            "INSERT INTO profiles (id, email) VALUES ('emp-1','employee@example.com')"
        ))
        conn.execute(text(
            "INSERT INTO cases (id, origin_country_code, dest_country_code, "
            "target_move_date, actual_move_date, status, employee_id, hr_owner_id, created_at) "
            "VALUES ('case-1','FR','NO',:move,NULL,'active','emp-1',NULL,'2026-01-01')"
        ), {"move": MOVE.isoformat()})
    monkeypatch.setattr(sweep, "_engine", lambda: engine)
    return engine


def _count(engine, table):
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()


def test_dry_run_reports_but_writes_nothing(db):
    result = sweep.run_corridor_deadline_sweep(today=OPENS, dry_run=True)

    assert result["cases_scanned"] == 1
    assert result["alerts_in_window"] == 1
    assert result["cases_skipped"] == 0
    entry = result["would_fire"][0]
    assert entry["step_id"] == "EEA_POLICE_REGISTRATION"
    assert entry["event_uid"] == f"case-1|EEA_POLICE_REGISTRATION|{DUE.isoformat()}"
    assert "window" in entry["subject"]

    assert _count(db, "corridor_deadline_events") == 0, "dry run must not write"
    assert _count(db, "notification_outbox") == 0, "dry run must not send"


def test_a_real_run_writes_the_outbox_row_and_the_ledger_row(db):
    result = sweep.run_corridor_deadline_sweep(today=OPENS)
    assert result["fired"] == 1
    assert result["no_contact"] == 0 and result["errors"] == 0

    with db.connect() as conn:
        ledger = conn.execute(text("SELECT * FROM corridor_deadline_events")).mappings().one()
        outbox = conn.execute(text("SELECT * FROM notification_outbox")).mappings().one()

    assert ledger["event_uid"] == f"case-1|EEA_POLICE_REGISTRATION|{DUE.isoformat()}"
    assert ledger["status"] == "fired"
    assert ledger["tag_name"] == "relopass-deadline-eea-police-registration-no"
    assert ledger["jurisdiction"] == "NOR", "the rule set's owner is recorded, not inferred later"
    assert str(ledger["due_date"]) == DUE.isoformat()
    assert ledger["lead_days"] == 30

    assert outbox["to_email"] == "employee@example.com"
    assert outbox["type"] == "corridor.deadline"
    assert outbox["status"] == "pending"


def test_a_second_run_the_same_day_fires_nothing(db):
    first = sweep.run_corridor_deadline_sweep(today=OPENS)
    second = sweep.run_corridor_deadline_sweep(today=OPENS)

    assert first["fired"] == 1
    assert second["fired"] == 0
    assert second["already_fired"] == 1
    assert _count(db, "notification_outbox") == 1, "the reader must not get it twice"


def test_every_day_of_the_window_fires_once_in_total(db):
    """The property that matters in production: the sweep runs daily for the whole
    30-day window and the person hears about it once."""
    day = OPENS
    while day <= DUE:
        sweep.run_corridor_deadline_sweep(today=day)
        day += timedelta(days=1)
    assert _count(db, "notification_outbox") == 1
    assert _count(db, "corridor_deadline_events") == 1


def test_a_case_with_no_recipient_records_no_contact_rather_than_going_quiet(db):
    with db.begin() as conn:
        conn.execute(text("UPDATE cases SET employee_id = NULL"))

    result = sweep.run_corridor_deadline_sweep(today=OPENS)
    assert result["no_contact"] == 1 and result["fired"] == 0

    with db.connect() as conn:
        row = conn.execute(text("SELECT * FROM corridor_deadline_events")).mappings().one()
    assert row["status"] == "no_contact"
    assert row["detail"], "a failure with no stated reason is not much of an audit trail"
    assert _count(db, "notification_outbox") == 0


def test_a_case_with_no_move_date_is_reported_as_skipped_with_its_reason(db):
    with db.begin() as conn:
        conn.execute(text("UPDATE cases SET target_move_date = NULL"))

    result = sweep.run_corridor_deadline_sweep(today=OPENS)
    assert result["cases_skipped"] == 1
    assert result["alerts_in_window"] == 0
    assert result["skips"][0]["reason"] == "no target_move_date or actual_move_date on the case"
    assert _count(db, "corridor_deadline_events") == 0
