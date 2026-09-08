"""End-to-end regression: HR dashboard list returns the SAME corridor as the
case-detail view, even when relocation_cases.home_country / host_country are
stale relative to the linked employee profile's movePlan.

Reproduces the bug reported for case 3c6fab7a-0fdd-44ab-8437-216ff09e82bf
where the dashboard showed "France -> Germany" while the case detail showed
"Oslo, Norway -> Singapore".

The test seeds minimal rows (one assignment + relocation_case +
employee_profile) directly via the db API and overrides FastAPI auth so it
exercises the real HTTP handler at GET /api/hr/assignments without booting
the legacy demo seed flow (which is sqlite-incompatible).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import text

from backend import database

# Make sure schema exists; init_db() is idempotent and safe to re-run regardless
# of whether the engine was already bound by an earlier import.
database.db.init_db()

from backend.main import app, get_current_user  # noqa: E402

db = database.db
client = TestClient(app)

ADMIN_USER = {
    "id": "admin-corridor-test",
    "email": "admin-corridor-test@example.com",
    "role": "ADMIN",
    "is_admin": True,
    "name": "Corridor Admin",
}


def setup_module(_module):
    app.dependency_overrides[get_current_user] = lambda: ADMIN_USER


def teardown_module(_module):
    app.dependency_overrides.pop(get_current_user, None)


def _seed(case_id: str, profile_json: str, employee_movePlan: dict | None,
          stored_home: str | None, stored_host: str | None) -> str:
    """Insert a relocation_case + case_assignment (+optional employee_profile)
    and return the assignment id."""
    assignment_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO relocation_cases (id, hr_user_id, profile_json, created_at, updated_at, "
                "company_id, employee_id, status, stage, host_country, home_country) VALUES "
                "(:id, :hr, :pj, :ca, :ua, NULL, NULL, 'in_progress', 'docs', :host, :home)"
            ),
            {
                "id": case_id,
                "hr": ADMIN_USER["id"],
                "pj": profile_json,
                "ca": now,
                "ua": now,
                "host": stored_host,
                "home": stored_home,
            },
        )
        conn.execute(
            text(
                "INSERT INTO case_assignments "
                "(id, case_id, canonical_case_id, hr_user_id, employee_user_id, employee_identifier, status, "
                "created_at, updated_at) "
                "VALUES (:id, :cid, :cid, :hr, NULL, :ident, 'assigned', :ca, :ua)"
            ),
            {
                "id": assignment_id,
                "cid": case_id,
                "hr": ADMIN_USER["id"],
                "ident": f"emp-{assignment_id[:8]}@example.com",
                "ca": now,
                "ua": now,
            },
        )
        if employee_movePlan is not None:
            conn.execute(
                text(
                    "INSERT INTO wizard_employee_profiles (assignment_id, profile_json, updated_at) "
                    "VALUES (:aid, :pj, :ua)"
                ),
                {
                    "aid": assignment_id,
                    "pj": json.dumps({"movePlan": employee_movePlan}),
                    "ua": now,
                },
            )
    return assignment_id


def _row_for(assignment_id: str) -> dict:
    res = client.get("/api/hr/assignments", params={"limit": 100, "offset": 0})
    assert res.status_code == 200, res.text
    rows = res.json().get("assignments") or []
    found = next((r for r in rows if r.get("id") == assignment_id), None)
    assert found is not None, f"assignment {assignment_id} missing from list"
    return found


def test_employee_movePlan_overrides_stale_stored_columns():
    """Reproduces the bug: stored cols France/Germany, but movePlan says
    Oslo, Norway / Singapore. The dashboard list should show the latter."""
    aid = _seed(
        case_id=f"case-bug-{uuid.uuid4().hex[:8]}",
        profile_json=json.dumps(
            {"relocationBasics": {"originCountry": "Norway", "destCountry": "Singapore"}}
        ),
        employee_movePlan={"origin": "Oslo, Norway", "destination": "Singapore"},
        stored_home="France",
        stored_host="Germany",
    )
    case_in_list = _row_for(aid).get("case") or {}
    assert case_in_list.get("home_country") == "Oslo, Norway", case_in_list
    assert case_in_list.get("host_country") == "Singapore", case_in_list


def test_relocation_basics_overrides_stored_columns_when_no_employee_profile():
    aid = _seed(
        case_id=f"case-rb-{uuid.uuid4().hex[:8]}",
        profile_json=json.dumps(
            {"relocationBasics": {"originCountry": "Norway", "destCountry": "Singapore"}}
        ),
        employee_movePlan=None,
        stored_home="France",
        stored_host="Germany",
    )
    case_in_list = _row_for(aid).get("case") or {}
    assert case_in_list.get("home_country") == "Norway", case_in_list
    assert case_in_list.get("host_country") == "Singapore", case_in_list


def test_falls_back_to_stored_columns_when_no_profile_signals():
    aid = _seed(
        case_id=f"case-stale-{uuid.uuid4().hex[:8]}",
        profile_json="{}",
        employee_movePlan=None,
        stored_home="Singapore",
        stored_host="New York, USA",
    )
    case_in_list = _row_for(aid).get("case") or {}
    assert case_in_list.get("home_country") == "Singapore", case_in_list
    assert case_in_list.get("host_country") == "New York, USA", case_in_list


def test_response_does_not_leak_profile_json_blob():
    """profile_json is fetched internally to resolve the corridor but must
    not be exposed in the API response (it was never in the contract)."""
    aid = _seed(
        case_id=f"case-leak-{uuid.uuid4().hex[:8]}",
        profile_json=json.dumps({"relocationBasics": {"originCountry": "Norway"}}),
        employee_movePlan={"origin": "Oslo, Norway", "destination": "Singapore"},
        stored_home="France",
        stored_host="Germany",
    )
    case_in_list = _row_for(aid).get("case") or {}
    assert "profile_json" not in case_in_list, case_in_list
