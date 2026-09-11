"""AIQ-2268 — duty-of-care board: classifier honesty + company scoping.

The load-bearing tenant test evaluates the same SQL the service runs against a
two-company SQLite fixture. Empty-company and route-registration tests mount
``backend.main:app`` and override ``backend.app.auth_deps``.
"""
from __future__ import annotations

import os
from datetime import date

import pytest
from sqlalchemy import create_engine, text
from fastapi.testclient import TestClient

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.app.services.duty_of_care_service import (  # noqa: E402
    AMBER,
    GREEN,
    NOT_TRACKED,
    RED,
    UNKNOWN,
    classify_permit,
    classify_row,
    list_duty_of_care_board,
    overall_rating,
)
from backend.main import app  # noqa: E402
from backend.app.auth_deps import get_current_user, get_org_id_for_hr_user  # noqa: E402

TODAY = date(2026, 9, 11)

SCHEMA = """
CREATE TABLE relocation_cases (
    id TEXT PRIMARY KEY,
    company_id TEXT,
    employee_id TEXT,
    host_country TEXT,
    home_country TEXT,
    expected_start_date TEXT,
    status TEXT,
    archived_at TEXT
);
CREATE TABLE case_assignments (
    id TEXT PRIMARY KEY,
    case_id TEXT,
    canonical_case_id TEXT,
    employee_identifier TEXT,
    employee_first_name TEXT,
    employee_last_name TEXT,
    expected_start_date TEXT
);
CREATE TABLE immigration_cases (
    id TEXT PRIMARY KEY,
    case_id TEXT,
    permit_type TEXT,
    status TEXT,
    permit_expiry_date TEXT
);
CREATE TABLE compliance_rules (
    id TEXT PRIMARY KEY,
    severity TEXT
);
CREATE TABLE compliance_alerts (
    id TEXT PRIMARY KEY,
    case_id TEXT,
    rule_id TEXT,
    status TEXT
);
CREATE TABLE case_requirement_checklist_state (
    id TEXT PRIMARY KEY,
    case_id TEXT,
    requirement_id TEXT,
    completed INTEGER
);
"""


def _classify(**kwargs):
    defaults = dict(
        has_immigration_row=True,
        permit_expiry=date(2026, 12, 1),
        permit_type="work_permit",
        has_critical_alert=False,
        checklist_item_count=2,
        checklist_completed_count=2,
        expected_start=date(2026, 11, 1),
        today=TODAY,
    )
    defaults.update(kwargs)
    return classify_row(**defaults)


class TestClassifier:
    def test_permit_expired_is_red(self):
        s = _classify(permit_expiry=date(2026, 9, 1))
        assert s.permit == RED
        assert s.overall == RED

    def test_permit_within_30_days_is_red(self):
        s = _classify(permit_expiry=date(2026, 10, 11))
        assert s.permit == RED
        assert s.overall == RED

    def test_permit_within_60_days_is_amber(self):
        s = _classify(permit_expiry=date(2026, 10, 21))
        assert s.permit == AMBER
        assert s.overall == AMBER

    def test_open_critical_alert_is_red(self):
        s = _classify(has_critical_alert=True, permit_expiry=date(2027, 1, 1))
        assert s.alert == RED
        assert s.overall == RED

    def test_missing_immigration_row_permit_is_unknown_not_green(self):
        s = _classify(has_immigration_row=False, permit_expiry=None)
        assert s.permit == UNKNOWN
        assert s.permit != GREEN
        assert s.overall != GREEN

    def test_incomplete_checklist_is_amber(self):
        s = _classify(
            permit_expiry=date(2027, 1, 1),
            checklist_item_count=3,
            checklist_completed_count=1,
        )
        assert s.checklist == AMBER
        assert s.overall == AMBER

    def test_all_clear_is_green(self):
        s = _classify(permit_expiry=date(2027, 1, 1))
        assert s.permit == GREEN
        assert s.alert == GREEN
        assert s.checklist == GREEN
        assert s.overall == GREEN

    def test_untracked_signals_never_serialize_green(self):
        s = _classify(permit_expiry=date(2027, 1, 1))
        assert s.a1 == NOT_TRACKED
        assert s.medical == NOT_TRACKED
        assert s.insurance == NOT_TRACKED
        assert GREEN not in (s.a1, s.medical, s.insurance)

    def test_untracked_only_row_is_not_green(self):
        assert overall_rating(
            permit=UNKNOWN,
            alert=GREEN,
            checklist=UNKNOWN,
            a1=NOT_TRACKED,
            medical=NOT_TRACKED,
            insurance=NOT_TRACKED,
        ) != GREEN
        assert classify_permit(
            has_immigration_row=False, permit_expiry=None, today=TODAY
        ) == UNKNOWN


def _seed_two_companies(conn):
    conn.execute(
        text(
            "INSERT INTO relocation_cases "
            "(id, company_id, employee_id, host_country, home_country, "
            " expected_start_date, status, archived_at) VALUES "
            "('case-a', 'co-a', 'emp-a', 'ES', 'IE', '2026-11-01', 'assigned', NULL),"
            "('case-b', 'co-b', 'emp-b', 'DE', 'FR', '2026-11-01', 'assigned', NULL)"
        )
    )
    conn.execute(
        text(
            "INSERT INTO immigration_cases "
            "(id, case_id, permit_type, status, permit_expiry_date) VALUES "
            "('imm-a', 'case-a', 'work_permit', 'granted', '2027-01-01'),"
            "('imm-b', 'case-b', 'work_permit', 'granted', '2026-09-01')"
        )
    )
    conn.execute(
        text(
            "INSERT INTO case_assignments "
            "(id, case_id, canonical_case_id, employee_identifier, "
            " employee_first_name, employee_last_name, expected_start_date) VALUES "
            "('asg-a', 'case-a', 'case-a', 'a@co-a.com', 'Ada', 'Alpha', NULL),"
            "('asg-b', 'case-b', 'case-b', 'b@co-b.com', 'Bea', 'Beta', NULL)"
        )
    )


class TestCompanyScopingSql:
    def test_company_a_never_sees_company_b_case_ids(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            for stmt in SCHEMA.strip().split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
            _seed_two_companies(conn)
            rows_a = list_duty_of_care_board(conn, "co-a", today=TODAY)
            rows_b = list_duty_of_care_board(conn, "co-b", today=TODAY)
        ids_a = {r["case_id"] for r in rows_a}
        ids_b = {r["case_id"] for r in rows_b}
        assert ids_a == {"case-a"}
        assert "case-b" not in ids_a
        assert ids_b == {"case-b"}
        assert "case-a" not in ids_b
        assert rows_a[0]["employee_name"] == "Ada Alpha"
        assert rows_b[0]["employee_name"] == "Bea Beta"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_org_id_for_hr_user, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_route_registered_on_prod_app():
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/hr/duty-of-care" in paths


def test_empty_company_returns_empty_board(client: TestClient):
    app.dependency_overrides[get_org_id_for_hr_user] = lambda: ""
    resp = client.get("/api/hr/duty-of-care")
    assert resp.status_code == 200
    assert resp.json() == {"cases": []}


def test_employee_is_rejected(client: TestClient):
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u1",
        "role": "employee",
        "email": "e@example.com",
    }
    resp = client.get("/api/hr/duty-of-care")
    assert resp.status_code == 403
