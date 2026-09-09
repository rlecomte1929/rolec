"""AIQ-2104 [ATT-2.2] — create_attestation accepts promotion_policy + advance_review_status.

The whole point of this change is that it is INVISIBLE unless you opt in, so most of these
tests are about what did NOT change. App is mounted from `backend.main` (the entrypoint
uvicorn actually boots) and auth is overridden on `backend.app.auth_deps.require_admin` —
the reference the router imports; overriding the same-named function in `backend.main`
silently never fires (CLAUDE.md).
"""
import os
import uuid
from datetime import datetime

import pytest

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import models  # noqa: E402
from backend.app.auth_deps import require_admin  # noqa: E402
from backend.app.db import SessionLocal, engine, Base  # noqa: E402
from backend.app.services.attestation_tokens import content_hash  # noqa: E402
from backend.main import app  # noqa: E402

ADMIN = {"id": "admin-1", "email": "admin@relopass.com", "is_admin": True, "role": "ADMIN"}

client = TestClient(app)


@pytest.fixture(autouse=True)
def _admin_auth():
    app.dependency_overrides[require_admin] = lambda: ADMIN
    yield
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture(autouse=True)
def _tables():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def corridor():
    """2 approved legal rows + 1 PENDING legal row + 1 approved operational (HOUSING) row.

    The pending row is what `advance_review_status` is supposed to pull in; the HOUSING row
    is the control proving the pillar filter still applies on the widened path.
    """
    country = f"ZTEST_{uuid.uuid4().hex[:8]}"
    rows = [
        ("RESIDENCE", "Police registration", "Register with the police.", "approved"),
        ("IDENTITY", "D-number", "Apply for a D-number.", "approved"),
        ("EMPLOYMENT", "Tax card (not yet published)", "Obtain a tax card.", "pending"),
        ("HOUSING", "Housing contract", "Secure a contract.", "approved"),
    ]
    ids = {}
    with SessionLocal() as db:
        for pillar, title, desc, review in rows:
            rid = str(uuid.uuid4())
            db.add(models.RequirementItem(
                id=rid, country_code=country, purpose="employment", pillar=pillar,
                title=title, description=desc, severity="WARN", owner="EMPLOYEE",
                required_fields_json="[]",
                citations_json='[{"url": "https://example.test/src"}]',
                verification_status="representative", review_status=review,
                last_verified_at=datetime.utcnow(),
            ))
            ids[title] = rid
        db.commit()
    return {"country": country, "ids": ids}


def _create(country, **kw):
    body = {"country_code": country, "purpose": "employment",
            "reviewer_org": "Example Legal LLP", "reviewer_name": "A Reviewer",
            "reviewer_email": "counsel@example.test"}
    body.update(kw)
    return client.post("/api/admin/attestations", json=body)


def _row(request_id):
    with SessionLocal() as db:
        return db.get(models.CorridorAttestationRequest, request_id)


# ── the invariant: defaults change nothing ─────────────────────────────────────
def test_default_create_stores_the_conservative_policy(corridor):
    r = _create(corridor["country"])
    assert r.status_code == 201, r.text
    row = _row(r.json()["request"]["id"])
    assert row.promotion_policy == "manual"
    assert row.advance_review_status is False


def test_default_create_snapshots_exactly_the_approved_legal_rows(corridor):
    """Unchanged from before ATT-2.2: 2 approved legal rows. Not the pending one, not HOUSING."""
    r = _create(corridor["country"])
    titles = sorted(i["title"] for i in r.json()["request"]["items"])
    assert titles == ["D-number", "Police registration"]


def test_the_admin_response_gains_no_new_keys(corridor):
    """The DTO shape is a contract the frontend's TS types mirror field-for-field.

    Persisting the two new columns must not leak them into the response — a new key is a
    silent contract change for every existing consumer, and these fields are admin INTENT,
    not something a reader needs.
    """
    r = _create(corridor["country"])
    req = r.json()["request"]
    assert "promotion_policy" not in req
    assert "advance_review_status" not in req


# ── opt-in: the policy is recorded ─────────────────────────────────────────────
def test_promotion_policy_is_persisted_when_named(corridor):
    r = _create(corridor["country"], promotion_policy="auto_on_sign")
    assert r.status_code == 201, r.text
    assert _row(r.json()["request"]["id"]).promotion_policy == "auto_on_sign"


def test_an_out_of_vocabulary_policy_is_refused_at_the_boundary(corridor):
    """422, and nothing written.

    Enforced twice on purpose. The Literal annotation rejects it here; the database CHECK
    (ck_cap_promotion_policy) is the authority underneath. Asserting 422 rather than
    "any 4xx/5xx" is the point of the test: measured on Postgres, letting it reach the
    CHECK raises psycopg2.errors.CheckViolation out of the endpoint unhandled — a 500
    whose DETAIL renders the entire failing row, content snapshot and all.
    """
    r = _create(corridor["country"], promotion_policy="publish_everything")
    assert r.status_code == 422, r.text
    with SessionLocal() as db:
        assert db.query(models.CorridorAttestationRequest).filter(
            models.CorridorAttestationRequest.country_code == corridor["country"]
        ).count() == 0


def test_the_database_check_is_still_the_backstop(corridor):
    """Bypass the API and write straight to the table — the CHECK must still refuse.

    Postgres only: ck_cap_promotion_policy lives in migration 20261120000000, not in the
    model, so on SQLite this would pass vacuously.

    ATT-2.5 / AIQ-2107: that skip is the coverage, not a hole we paper over. The default
    pytest lane is SQLite. A skipped CHECK test must not be read as "the CHECK is tested."
    The CI Postgres job is the only place this assertion runs.
    """
    if engine.dialect.name != "postgresql":
        pytest.skip("ck_cap_promotion_policy is a Postgres CHECK; not present on SQLite")
    import sqlalchemy
    with SessionLocal() as db:
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            db.add(models.CorridorAttestationRequest(
                id=str(uuid.uuid4()), country_code=corridor["country"], purpose="employment",
                scope="legal", status="draft", requested_by="test",
                content_snapshot_hash="x", content_snapshot_json=[],
                promotion_policy="publish_everything",
            ))
            db.commit()


# ── opt-in: the snapshot widens ────────────────────────────────────────────────
def test_advance_review_status_pulls_pending_rows_into_the_snapshot(corridor):
    r = _create(corridor["country"], advance_review_status=True)
    assert r.status_code == 201, r.text
    titles = sorted(i["title"] for i in r.json()["request"]["items"])
    assert titles == ["D-number", "Police registration", "Tax card (not yet published)"]
    assert _row(r.json()["request"]["id"]).advance_review_status is True


def test_widening_changes_the_content_hash(corridor):
    """The hash is what a signature binds to, so a wider checklist must hash differently."""
    narrow = _create(corridor["country"]).json()["request"]["content_snapshot_hash"]
    wide = _create(corridor["country"], advance_review_status=True).json()["request"]["content_snapshot_hash"]
    assert narrow != wide


def test_the_widened_hash_is_the_canonical_hash_of_the_stored_snapshot(corridor):
    """Not just 'different' — the right value, computed by the same canonical function.

    Rebuilt from `content_snapshot_json` rather than from the response: the checklist DTO
    exposes the attestation-item id, not `requirement_item_id`, so the response cannot
    reconstruct the canonical payload. Hashing the STORED snapshot is the stronger claim
    anyway — it is what a signature is actually bound to.
    """
    r = _create(corridor["country"], advance_review_status=True)
    row = _row(r.json()["request"]["id"])
    assert len(row.content_snapshot_json) == 3
    assert row.content_snapshot_hash == content_hash(row.content_snapshot_json)
    assert r.json()["request"]["content_snapshot_hash"] == row.content_snapshot_hash


def test_the_pending_row_is_actually_in_the_stored_snapshot(corridor):
    """The widened path must snapshot the pending row's real claim, not an empty shell."""
    r = _create(corridor["country"], advance_review_status=True)
    row = _row(r.json()["request"]["id"])
    pending = [i for i in row.content_snapshot_json
               if i["requirement_item_id"] == corridor["ids"]["Tax card (not yet published)"]]
    assert len(pending) == 1
    assert pending[0]["claim"] == "Obtain a tax card."
    assert pending[0]["source_url"] == "https://example.test/src"


# ── the pillar filter survives the widening ────────────────────────────────────
def test_operational_pillars_stay_excluded_on_the_widened_path(corridor):
    r = _create(corridor["country"], advance_review_status=True)
    titles = [i["title"] for i in r.json()["request"]["items"]]
    assert "Housing contract" not in titles


def test_explicit_ids_still_override_the_pillar_filter(corridor):
    """An explicit list is a deliberate scope decision and must not be silently trimmed."""
    r = _create(corridor["country"], requirement_item_ids=[corridor["ids"]["Housing contract"]])
    titles = [i["title"] for i in r.json()["request"]["items"]]
    assert titles == ["Housing contract"]


def test_explicit_ids_are_still_bounded_by_review_status(corridor):
    """Naming a pending id without the flag selects nothing — 422, not a silent promotion."""
    r = _create(corridor["country"],
                requirement_item_ids=[corridor["ids"]["Tax card (not yet published)"]])
    assert r.status_code == 422
    r2 = _create(corridor["country"], advance_review_status=True,
                 requirement_item_ids=[corridor["ids"]["Tax card (not yet published)"]])
    assert r2.status_code == 201
    assert [i["title"] for i in r2.json()["request"]["items"]] == ["Tax card (not yet published)"]
