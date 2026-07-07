"""Public corridor-requirements read model (Audos seam) — no auth, no PII.

Located in backend/tests/ (NOT backend/app/routers/ as the task text suggested) because
backend/pytest.ini sets `testpaths = tests` — a co-located router test would not be
collected by CI, defeating the "pytest passes; new test included" gate.

crud.list_requirements is monkeypatched to canned NORWAY seed rows (mirroring
backend/seeds/requirements/long_term_only.yaml) so the test is deterministic and does not
depend on the SQLite test DB being seeded. The real apply_rules (assignment-type filter)
and the response mapping ARE exercised. App is mounted from backend.main (the prod-served
entrypoint) so the test also proves the route reached the prod registration.
"""
import json
import os
from types import SimpleNamespace

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
# App-mounted harness: conftest mocks backend.database, so the query-counter listener
# can't attach to the mocked engine unless it's disabled.
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.app.routers import public_corridor  # noqa: E402

client = TestClient(app)


def _norway_seed():
    """Canned NORWAY requirement_items rows (mirror long_term_only.yaml; gated LTA/PERMANENT)."""
    common = dict(
        country_code="NORWAY", purpose="employment", severity="WARN", owner="EMPLOYEE",
        required_fields_json="[]", citations_json="[]",
        applies_to_assignment_types_json='["LTA","PERMANENT"]', verification_status="representative",
    )
    return [
        SimpleNamespace(
            id="no-residence", pillar="RESIDENCE",
            title="Residence registration (folkeregister)",
            description=("Register at the National Registry (folkeregister) to obtain a national ID "
                         "number or D-number. Indicative — confirm with Skatteetaten."),
            **common,
        ),
        SimpleNamespace(
            id="no-housing", pillar="HOUSING",
            title="Long-term housing contract",
            description="Secure a long-term housing contract. Indicative — confirm with authorities.",
            **common,
        ),
        SimpleNamespace(
            id="no-social", pillar="SOCIAL_SECURITY",
            title="National Insurance registration (folketrygden)",
            description="Register with the National Insurance Scheme (folketrygden) via NAV.",
            **common,
        ),
    ]


def _patch_seed(monkeypatch):
    monkeypatch.setattr(
        public_corridor.crud, "list_requirements",
        lambda db, country, purpose: _norway_seed() if country == "NORWAY" else [],
    )


def test_fr_no_lta_returns_generic_requirements_no_auth(monkeypatch):
    _patch_seed(monkeypatch)
    # No Authorization header at all — must still 200 (public).
    resp = client.get("/api/public/corridor-requirements?from=FR&to=NO&employee_type=LTA")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["corridor"] == {"from": "FR", "to": "NORWAY"}
    assert body["employee_type"] == "LTA"
    assert "generated_at" in body

    reqs = body["requirements"]
    assert isinstance(reqs, list) and len(reqs) >= 1
    for r in reqs:  # exact response shape per requirement
        assert set(r.keys()) == {"key", "label", "description", "timing", "non_obvious", "category", "source"}
    # the D-number / folkeregister residence item the engine DOES carry for NO/LTA
    blob = json.dumps(reqs).lower()
    assert "d-number" in blob or "folkeregister" in blob
    assert any(r["category"] == "RESIDENCE" for r in reqs)

    # data minimization: no case/user/PII fields leak into the public payload
    full = json.dumps(body).lower()
    for forbidden in ("email", "reporter", "user_id", "case_id", "caseid", "passport",
                      "statusforcase", "full_name", "fullname", "draft_json"):
        assert forbidden not in full, f"PII/case field '{forbidden}' leaked"


def test_cors_wildcard_header(monkeypatch):
    _patch_seed(monkeypatch)
    resp = client.get("/api/public/corridor-requirements?from=FR&to=NO&employee_type=LTA")
    assert resp.headers.get("access-control-allow-origin") == "*"


def test_sta_waives_lta_items_with_coverage_note(monkeypatch):
    _patch_seed(monkeypatch)
    resp = client.get("/api/public/corridor-requirements?from=FR&to=NO&employee_type=STA")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Every NO item is LTA/PERMANENT-gated → STA gets an empty list + an explicit note.
    assert body["requirements"] == []
    assert body["coverage_note"]
    assert "Residence registration (folkeregister)" in body["waived_for_assignment_type"]


def test_invalid_employee_type_422(monkeypatch):
    _patch_seed(monkeypatch)
    # lowercase policy-enum value is the wrong vocabulary for this engine → rejected.
    resp = client.get("/api/public/corridor-requirements?from=FR&to=NO&employee_type=long_term")
    assert resp.status_code == 422
