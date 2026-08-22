"""AIQ-2109 [ATT-3.2] — case-scoped attestation: snapshot what ONE case is actually served.

The load-bearing assertion in this file is the PII one. A case carries employee and company
data; counsel must see none of it. Everything else here exists to make that assertion mean
something — if the snapshot were empty or wrong, "no PII" would be trivially true.

App is mounted from `backend.main` and auth overridden on `backend.app.auth_deps.require_admin`
— the reference the router imports (CLAUDE.md).
"""
import importlib
import json
import os
import sys
import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import inspect, text

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

# backend/conftest.py installs a MagicMock at sys.modules["backend.database"] so unit tests
# need no DB. This file exercises the REAL canonical case-id resolver (db.resolve_case_ids):
# under the mock every id "resolves" to a MagicMock, so the 404 path could never be tested.
#
# Borrow the real module, take the Database class, then PUT THE MOCK BACK immediately.
# Leaving the real module installed — the documented escape hatch — pollutes full-suite
# ordering exactly as backend/conftest.py warns: pytest imports every test module during
# collection, so any module collected after this one binds the real `db` and breaks.
# Measured: it took test_catalog_promotion.py from 4 passing to 4 failing. Restoring here,
# at import time, means the mock is back before the next module is collected.
_borrowed = None
if isinstance(sys.modules.get("backend.database"), MagicMock):
    _mock_module = sys.modules.pop("backend.database")
    try:
        _borrowed = importlib.import_module("backend.database")
    finally:
        sys.modules["backend.database"] = _mock_module
else:
    _borrowed = importlib.import_module("backend.database")
Database = _borrowed.Database

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import models  # noqa: E402
from backend.app.auth_deps import require_admin  # noqa: E402
from backend.app.db import SessionLocal, engine, Base  # noqa: E402
from backend.app.services.attestation_tokens import content_hash  # noqa: E402
from backend.main import app  # noqa: E402
import backend.app.routers.attestation as attestation_router  # noqa: E402

#: A genuine Database pointed at the app's own test engine, so the resolver runs real SQL
#: against the same SQLite the fixtures seed. Instantiated once; `engine` is overridden
#: because Database() binds the module-level engine built at import time.
main_db = Database()
main_db.engine = engine

ADMIN = {"id": "admin-1", "email": "admin@relopass.com", "is_admin": True, "role": "ADMIN"}
client = TestClient(app)

#: Real employee/company PII seeded into the case, so the PII assertion has something to
#: actually find if the boundary ever leaks. None of these strings may reach counsel.
PII = {
    "employee_name": "Ingrid Solberg-Testcase",
    "employee_email": "ingrid.solberg@acme-testcase.example",
    "passport": "NO-PASSPORT-99887766",
    "company": "Acme Testcase Holdings AS",
    "salary": "1234567",
    "home_address": "17 Testcase Gate, Oslo",
}


@pytest.fixture(autouse=True)
def _admin_auth():
    app.dependency_overrides[require_admin] = lambda: ADMIN
    yield
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture(autouse=True)
def _real_resolver(monkeypatch):
    """Point the router at the real resolver rather than conftest's MagicMock."""
    monkeypatch.setattr(attestation_router, "main_db", main_db)
    yield


@pytest.fixture(autouse=True)
def _tables():
    Base.metadata.create_all(bind=engine)
    # `case_assignments` is not an app/models.py table, so create_all does not make it.
    # The resolver does `SELECT * FROM case_assignments WHERE (canonical_case_id = :cid
    # OR case_id = :cid OR id = :cid)`, so these three columns are what it needs.
    with main_db.engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS case_assignments (
                id TEXT PRIMARY KEY,
                case_id TEXT,
                canonical_case_id TEXT
            )
        """))
    yield


def _insert_assignment(assignment_id: str, cid: str) -> None:
    """Insert an assignment row into whatever `case_assignments` actually exists.

    The CREATE above is `IF NOT EXISTS`, so in a FULL-SUITE run another module may have
    already created a much wider `case_assignments` — and the real one carries NOT NULL
    columns this file knows nothing about (`hr_user_id` was the one that caught this).
    A fixed three-column INSERT passes when this file runs alone and dies with
    `NOT NULL constraint failed` when it does not, which is the worst kind of test: green
    in isolation, red only in the run that matters.

    So discover the shape at runtime and fill every NOT NULL column that has no default.
    """
    insp = inspect(main_db.engine)
    cols = {c["name"]: c for c in insp.get_columns("case_assignments")}

    values = {"id": assignment_id, "case_id": cid, "canonical_case_id": cid}
    for name, col in cols.items():
        if name in values:
            continue
        if col.get("nullable", True) or col.get("default") is not None:
            continue
        # A required column this test does not model. It only has to be non-null and
        # unique-ish; nothing under test reads it.
        values[name] = f"test-{uuid.uuid4().hex[:12]}"

    usable = {k: v for k, v in values.items() if k in cols}
    columns = ", ".join(usable)
    binds = ", ".join(f":{k}" for k in usable)
    with main_db.engine.begin() as conn:
        conn.execute(text(f"INSERT INTO case_assignments ({columns}) VALUES ({binds})"), usable)


def _seed_case(dest="Norway", purpose="employment", case_id=None):
    """A wizard case whose draft is stuffed with PII, plus its assignment row."""
    cid = case_id or str(uuid.uuid4())
    assignment_id = str(uuid.uuid4())
    draft = {
        "relocationBasics": {"destCountry": dest, "originCountry": "Spain", "purpose": purpose},
        # The PII a real case carries. Present on purpose.
        "employee": {
            "fullName": PII["employee_name"],
            "email": PII["employee_email"],
            "passportNumber": PII["passport"],
            "homeAddress": PII["home_address"],
        },
        "company": {"name": PII["company"], "annualSalary": PII["salary"]},
    }
    with SessionLocal() as db:
        db.add(models.Case(
            id=cid, draft_json=json.dumps(draft), dest_country=dest,
            origin_country="Spain", purpose=purpose, status="created",
        ))
        db.commit()
    _insert_assignment(assignment_id, cid)
    return {"case_id": cid, "assignment_id": assignment_id}


@pytest.fixture
def catalog():
    """Approved NORWAY/employment rows: 2 legal + 1 operational (HOUSING) control."""
    rows = [
        ("RESIDENCE", "Police registration (case-scope test)", "Register with the police within 3 months."),
        ("IDENTITY", "D-number (case-scope test)", "Apply for a D-number."),
        ("HOUSING", "Housing contract (case-scope test)", "Secure a long-term contract."),
    ]
    ids = {}
    with SessionLocal() as db:
        db.query(models.RequirementItem).filter(
            models.RequirementItem.country_code == "NORWAY").delete()
        for pillar, title, desc in rows:
            rid = str(uuid.uuid4())
            db.add(models.RequirementItem(
                id=rid, country_code="NORWAY", purpose="employment", pillar=pillar,
                title=title, description=desc, severity="WARN", owner="EMPLOYEE",
                required_fields_json="[]",
                citations_json='[{"url": "https://www.skatteetaten.no/en/example"}]',
                verification_status="representative", review_status="approved",
                last_verified_at=datetime.utcnow(),
            ))
            ids[title] = rid
        db.commit()
    return ids


def _create_case_attestation(case_id, **kw):
    body = {"case_id": case_id, "reviewer_org": "Example Legal LLP",
            "reviewer_name": "A Reviewer", "reviewer_email": "counsel@example.test"}
    body.update(kw)
    return client.post("/api/admin/attestations/case", json=body)


# ── the served set ─────────────────────────────────────────────────────────────
def test_a_case_request_snapshots_the_served_legal_rows(catalog):
    case = _seed_case()
    r = _create_case_attestation(case["case_id"])
    assert r.status_code == 201, r.text
    titles = sorted(i["title"] for i in r.json()["request"]["items"])
    assert titles == ["D-number (case-scope test)", "Police registration (case-scope test)"]


def test_the_operational_pillar_is_not_put_in_front_of_counsel(catalog):
    case = _seed_case()
    r = _create_case_attestation(case["case_id"])
    titles = [i["title"] for i in r.json()["request"]["items"]]
    assert "Housing contract (case-scope test)" not in titles


def test_scope_and_case_id_are_persisted(catalog):
    case = _seed_case()
    r = _create_case_attestation(case["case_id"])
    with SessionLocal() as db:
        row = db.get(models.CorridorAttestationRequest, r.json()["request"]["id"])
    assert row.scope == "case"
    assert str(row.case_id) == case["case_id"]


def test_the_assignment_id_resolves_to_the_same_case(catalog):
    """resolve_case_ids accepts all three id forms; the envelope must not care which."""
    case = _seed_case()
    by_case = _create_case_attestation(case["case_id"])
    by_assignment = _create_case_attestation(case["assignment_id"])
    assert by_assignment.status_code == 201, by_assignment.text
    assert (by_case.json()["request"]["content_snapshot_hash"]
            == by_assignment.json()["request"]["content_snapshot_hash"])


# ── the hash ───────────────────────────────────────────────────────────────────
def test_the_content_hash_is_stable_across_refetch(catalog):
    """Same case, same catalog, two requests — the signature-bound hash must not drift."""
    case = _seed_case()
    first = _create_case_attestation(case["case_id"]).json()["request"]["content_snapshot_hash"]
    second = _create_case_attestation(case["case_id"]).json()["request"]["content_snapshot_hash"]
    assert first == second


def test_the_stored_hash_is_the_canonical_hash_of_the_stored_snapshot(catalog):
    case = _seed_case()
    r = _create_case_attestation(case["case_id"])
    with SessionLocal() as db:
        row = db.get(models.CorridorAttestationRequest, r.json()["request"]["id"])
    assert len(row.content_snapshot_json) == 2
    assert row.content_snapshot_hash == content_hash(row.content_snapshot_json)


# ── THE PII BOUNDARY ───────────────────────────────────────────────────────────
def test_the_public_envelope_carries_zero_case_pii(catalog):
    """The one that matters. Counsel opens the token link and must see catalog content only.

    Asserted against the RAW response body, not against parsed fields, so a leak through a
    nested object or an unexpected key is caught too.
    """
    case = _seed_case()
    created = _create_case_attestation(case["case_id"])
    request_id = created.json()["request"]["id"]
    token = created.json()["review_token"]
    client.post(f"/api/admin/attestations/{request_id}/send")

    public = client.get(f"/api/public/attestations/{token}")
    assert public.status_code == 200, public.text
    body = public.text

    leaked = [k for k, v in PII.items() if v in body]
    assert leaked == [], f"case PII reached the public envelope: {leaked}"

    # The case id itself is not PII, but it identifies the person's file and has no reason
    # to be in a legal envelope either.
    assert case["case_id"] not in body
    assert case["assignment_id"] not in body


def test_no_case_pii_reaches_the_stored_snapshot_or_items(catalog):
    """Belt and braces: the leak would be just as real if it only sat in the database."""
    case = _seed_case()
    r = _create_case_attestation(case["case_id"])
    request_id = r.json()["request"]["id"]
    with SessionLocal() as db:
        row = db.get(models.CorridorAttestationRequest, request_id)
        items = db.query(models.CorridorAttestationItem).filter(
            models.CorridorAttestationItem.request_id == request_id).all()
        blob = json.dumps(row.content_snapshot_json) + "".join(
            f"{i.item_title}{i.claim_snapshot}{i.source_url_snapshot}{i.evidence_snapshot}"
            for i in items
        )
    leaked = [k for k, v in PII.items() if v in blob]
    assert leaked == [], f"case PII reached the snapshot/items: {leaked}"


def test_the_snapshot_keys_are_exactly_the_whitelist(catalog):
    """canonical_payload is a whitelist; the case path must not widen it."""
    case = _seed_case()
    r = _create_case_attestation(case["case_id"])
    with SessionLocal() as db:
        row = db.get(models.CorridorAttestationRequest, r.json()["request"]["id"])
    for item in row.content_snapshot_json:
        assert set(item.keys()) == {
            "requirement_item_id", "title", "claim", "source_url", "evidence"
        }


# ── clean failures, never a 500 ────────────────────────────────────────────────
def test_an_unknown_case_id_is_a_clean_404(catalog):
    r = _create_case_attestation(str(uuid.uuid4()))
    assert r.status_code == 404, r.text


def test_a_garbage_case_id_is_a_clean_404_not_a_database_error(catalog):
    r = _create_case_attestation("'; DROP TABLE case_assignments;--")
    assert r.status_code == 404, r.text


def test_a_non_uuid_case_id_is_a_clean_422_not_a_dataerror(catalog):
    """Measured in production: 7 of 1,840 wizard_cases ids are not uuid-shaped (six demo
    rows and a literal "undefined"). corridor_attestation_requests.case_id is `uuid`, so
    writing one of those raises a psycopg2 DataError out of the endpoint — a 500 whose
    DETAIL renders the failing row. Refused at the boundary instead.
    """
    case = _seed_case(case_id=f"demo-case-{uuid.uuid4().hex[:8]}-not-a-uuid")
    r = _create_case_attestation(case["case_id"])
    assert r.status_code == 422, r.text
    assert "uuid" in r.json()["detail"].lower()


def test_a_case_with_an_uncovered_destination_is_422_not_an_empty_envelope(catalog):
    """A destination with no catalog is a gap, not 'nothing is required'. Never send
    counsel an empty checklist that reads as a clean bill of health."""
    case = _seed_case(dest="Wakanda")
    r = _create_case_attestation(case["case_id"])
    assert r.status_code == 422, r.text
    assert r.json()["detail"]
