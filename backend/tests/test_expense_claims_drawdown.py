"""[AIQ-2271] Drawdown math + FX snapshot reproducibility for expense claims."""
from __future__ import annotations

import os
import uuid

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from datetime import date

from sqlalchemy import create_engine, text

from backend.app.services.expense_claim_drawdown import drawdown_for_case
from backend.app.services.fx_service import convert_with_snapshot, rate_between
from backend.app.services.policy_config_cap_compare import NORMALIZED_CURRENCY_AMOUNT

SCHEMA = """
CREATE TABLE expense_claims (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  company_id TEXT NOT NULL,
  employee_user_id TEXT,
  status TEXT NOT NULL,
  created_at TEXT
);
CREATE TABLE expense_claim_lines (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL,
  benefit_key TEXT NOT NULL,
  amount REAL NOT NULL,
  currency TEXT NOT NULL,
  cap_currency TEXT,
  fx_rate_to_cap REAL,
  fx_rate_date TEXT,
  amount_in_cap_currency REAL,
  created_at TEXT
);
CREATE TABLE fx_rates (
  id TEXT PRIMARY KEY,
  as_of_date TEXT NOT NULL,
  base_currency TEXT NOT NULL,
  quote_currency TEXT NOT NULL,
  rate REAL NOT NULL,
  source TEXT,
  UNIQUE (as_of_date, base_currency, quote_currency)
);
"""

INSTALL_CAP = {
    "benefit_key": "installation_allowance",
    "benefit_label": "Installation allowance",
    "normalized_cap_type": NORMALIZED_CURRENCY_AMOUNT,
    "normalized_amount": 3049,
    "currency_code": "EUR",
}


def _engine():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        for stmt in SCHEMA.split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))
    return engine


def _claim(conn, *, case_id, company_id, status, lines):
    cid = str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO expense_claims (id, case_id, company_id, status) "
            "VALUES (:id, :case_id, :org, :status)"
        ),
        {"id": cid, "case_id": case_id, "org": company_id, "status": status},
    )
    for line in lines:
        conn.execute(
            text(
                """
                INSERT INTO expense_claim_lines (
                    id, claim_id, benefit_key, amount, currency, cap_currency,
                    fx_rate_to_cap, amount_in_cap_currency
                ) VALUES (
                    :id, :claim_id, :benefit_key, :amount, :currency, :cap_currency,
                    :rate, :in_cap
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "claim_id": cid,
                **line,
            },
        )
    return cid


def test_drawdown_approved_lines_only():
    engine = _engine()
    with engine.begin() as conn:
        _claim(
            conn,
            case_id="c1",
            company_id="co-a",
            status="approved",
            lines=[
                {
                    "benefit_key": "installation_allowance",
                    "amount": 1000,
                    "currency": "EUR",
                    "cap_currency": "EUR",
                    "rate": 1.0,
                    "in_cap": 1000,
                }
            ],
        )
        _claim(
            conn,
            case_id="c1",
            company_id="co-a",
            status="approved",
            lines=[
                {
                    "benefit_key": "installation_allowance",
                    "amount": 549,
                    "currency": "EUR",
                    "cap_currency": "EUR",
                    "rate": 1.0,
                    "in_cap": 549,
                }
            ],
        )
        _claim(
            conn,
            case_id="c1",
            company_id="co-a",
            status="submitted",
            lines=[
                {
                    "benefit_key": "installation_allowance",
                    "amount": 999,
                    "currency": "EUR",
                    "cap_currency": "EUR",
                    "rate": 1.0,
                    "in_cap": 999,
                }
            ],
        )
        _claim(
            conn,
            case_id="c1",
            company_id="co-a",
            status="draft",
            lines=[
                {
                    "benefit_key": "installation_allowance",
                    "amount": 50,
                    "currency": "EUR",
                    "cap_currency": "EUR",
                    "rate": 1.0,
                    "in_cap": 50,
                }
            ],
        )
        _claim(
            conn,
            case_id="c1",
            company_id="co-a",
            status="rejected",
            lines=[
                {
                    "benefit_key": "installation_allowance",
                    "amount": 200,
                    "currency": "EUR",
                    "cap_currency": "EUR",
                    "rate": 1.0,
                    "in_cap": 200,
                }
            ],
        )
        rows = {r["benefit_key"]: r for r in drawdown_for_case(conn, "c1", [INSTALL_CAP])}
    item = rows["installation_allowance"]
    assert item["cap_amount"] == 3049
    assert item["claimed_approved"] == 1549
    assert item["remaining"] == 1500
    assert item["status"] == "within_budget"


def test_orphan_benefit_key_is_no_cap_not_zero():
    engine = _engine()
    with engine.begin() as conn:
        _claim(
            conn,
            case_id="c1",
            company_id="co-a",
            status="approved",
            lines=[
                {
                    "benefit_key": "unknown_perk",
                    "amount": 100,
                    "currency": "EUR",
                    "cap_currency": "EUR",
                    "rate": 1.0,
                    "in_cap": 100,
                }
            ],
        )
        rows = {r["benefit_key"]: r for r in drawdown_for_case(conn, "c1", [INSTALL_CAP])}
    assert rows["unknown_perk"]["status"] == "no_cap"
    assert rows["unknown_perk"]["remaining"] is None
    assert rows["unknown_perk"]["cap_amount"] is None


def test_over_budget_is_honest_negative_remaining():
    engine = _engine()
    with engine.begin() as conn:
        _claim(
            conn,
            case_id="c1",
            company_id="co-a",
            status="paid",
            lines=[
                {
                    "benefit_key": "installation_allowance",
                    "amount": 4000,
                    "currency": "EUR",
                    "cap_currency": "EUR",
                    "rate": 1.0,
                    "in_cap": 4000,
                }
            ],
        )
        rows = {r["benefit_key"]: r for r in drawdown_for_case(conn, "c1", [INSTALL_CAP])}
    item = rows["installation_allowance"]
    assert item["status"] == "over_budget"
    assert item["remaining"] == 3049 - 4000


def test_cross_currency_without_stored_rate_is_not_comparable():
    engine = _engine()
    with engine.begin() as conn:
        _claim(
            conn,
            case_id="c1",
            company_id="co-a",
            status="approved",
            lines=[
                {
                    "benefit_key": "installation_allowance",
                    "amount": 100,
                    "currency": "USD",
                    "cap_currency": "EUR",
                    "rate": None,
                    "in_cap": None,
                }
            ],
        )
        rows = {r["benefit_key"]: r for r in drawdown_for_case(conn, "c1", [INSTALL_CAP])}
    assert rows["installation_allowance"]["status"] == "not_comparable"
    assert rows["installation_allowance"]["remaining"] is None


def test_fx_snapshot_survives_live_rate_change():
    engine = _engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO fx_rates (id, as_of_date, base_currency, quote_currency, rate) "
                "VALUES ('r1', '2026-01-01', 'USD', 'EUR', 0.92)"
            )
        )
        amt, rate, as_of = convert_with_snapshot(1000, "USD", "EUR", conn)
        assert rate == 0.92
        assert amt == 920
        assert as_of == date(2026, 1, 1)
        stored = amt
        conn.execute(text("DELETE FROM fx_rates"))
        conn.execute(
            text(
                "INSERT INTO fx_rates (id, as_of_date, base_currency, quote_currency, rate) "
                "VALUES ('r2', '2026-09-11', 'USD', 'EUR', 0.50)"
            )
        )
        _claim(
            conn,
            case_id="c1",
            company_id="co-a",
            status="approved",
            lines=[
                {
                    "benefit_key": "installation_allowance",
                    "amount": 1000,
                    "currency": "USD",
                    "cap_currency": "EUR",
                    "rate": rate,
                    "in_cap": stored,
                }
            ],
        )
        rows = {r["benefit_key"]: r for r in drawdown_for_case(conn, "c1", [INSTALL_CAP])}
    assert rows["installation_allowance"]["claimed_approved"] == 920
    with engine.connect() as live_conn:
        live = convert_with_snapshot(1000, "USD", "EUR", live_conn)
    assert live[0] == 500  # live table changed, drawdown did not


def test_same_currency_rate_is_one():
    assert rate_between("EUR", "EUR") == 1.0
    amt, rate, _ = convert_with_snapshot(10, "EUR", "EUR", None)
    assert rate == 1.0
    assert amt == 10


def test_missing_snapshot_falls_back_to_hardcoded_table():
    engine = _engine()
    with engine.connect() as conn:
        amt, rate, _ = convert_with_snapshot(100, "USD", "EUR", conn)
    assert rate == 0.92
    assert amt == 92
