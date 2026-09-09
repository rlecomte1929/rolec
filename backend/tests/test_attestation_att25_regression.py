"""AIQ-2107 [ATT-2.5] — the four gaps ATT-2.2 / ATT-2.4 left open.

Existing files already cover the happy path and the refusals. This file only adds what
those suites do not: SQLite vs CHECK honesty, auto_on_sign against a zero-approved
corridor, a pre-feature row whose policy was defaulted not sent, and two signatures
on one request under auto_on_sign.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import models  # noqa: E402
from backend.app.auth_deps import require_admin  # noqa: E402
from backend.app.db import SessionLocal, engine, Base  # noqa: E402
from backend.app.routers.attestation import _latest_signature  # noqa: E402
from backend.main import app  # noqa: E402

ADMIN = {"id": "admin-1", "email": "admin@relopass.com", "is_admin": True, "role": "ADMIN"}
client = TestClient(app)
CREDENTIAL = "NO-BAR-1234"


@pytest.fixture(autouse=True)
def _admin_auth():
    app.dependency_overrides[require_admin] = lambda: ADMIN
    yield
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture(autouse=True)
def _tables():
    Base.metadata.create_all(bind=engine)
    yield


def _add_item(country, *, pillar, title, desc, review):
    rid = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(models.RequirementItem(
            id=rid, country_code=country, purpose="employment", pillar=pillar,
            title=title, description=desc, severity="WARN", owner="EMPLOYEE",
            required_fields_json="[]",
            citations_json='[{"url": "https://example.test/src"}]',
            verification_status="representative", review_status=review,
            last_verified_at=datetime.utcnow(),
        ))
        db.commit()
    return rid


def _create(country, **kw):
    body = {"country_code": country, "purpose": "employment",
            "reviewer_org": "Advokatfirmaet Example AS", "reviewer_name": "Kari Nordmann",
            "reviewer_email": "kari@example.no"}
    body.update(kw)
    return client.post("/api/admin/attestations", json=body)


def _open(country, **kw):
    r = _create(country, **kw)
    assert r.status_code == 201, r.text
    created = r.json()
    req_id, token = created["request"]["id"], created["review_token"]
    assert client.post(f"/api/admin/attestations/{req_id}/send").status_code == 200
    return req_id, token


def _decide(token):
    view = client.get(f"/api/public/attestations/{token}").json()
    for item in view["items"]:
        r = client.post(f"/api/public/attestations/{token}/items/{item['id']}",
                        json={"decision": "approved"})
        assert r.status_code == 200, r.text
    return client.get(f"/api/public/attestations/{token}").json()


def _sign(token, content_hash, credential=CREDENTIAL, signer_name="Kari Nordmann"):
    body = {"signer_name": signer_name, "signer_email": "kari@example.no",
            "signer_org": "Advokatfirmaet Example AS",
            "content_hash": content_hash, "agreed_to_disclaimer": True}
    if credential is not None:
        body["signer_credential"] = credential
    return client.post(f"/api/public/attestations/{token}/sign", json=body)


# ── 1. SQLite must not be mistaken for CHECK coverage ──────────────────────────
def test_the_sqlite_lane_does_not_claim_the_postgres_check():
    """Removing the skip without a PG lane would make a vacuous pass look like coverage."""
    src = Path(__file__).with_name("test_attestation_create_policy.py").read_text()
    assert 'pytest.skip("ck_cap_promotion_policy is a Postgres CHECK' in src
    if engine.dialect.name == "sqlite":
        assert engine.dialect.name != "postgresql"


# ── 2. auto_on_sign × zero approved items × advance_review_status ──────────────
def test_auto_on_sign_without_approved_rows_is_422_until_the_snapshot_widens():
    """Zero approved legal rows: default snapshot is empty → 422.

    advance_review_status is what pulls pending rows in. auto_on_sign alone must not
    invent a checklist.
    """
    country = f"ZNONE_{uuid.uuid4().hex[:8]}"
    _add_item(
        country, pillar="EMPLOYMENT", title="Tax card only",
        desc="Obtain a tax card.", review="pending",
    )
    r = _create(country, promotion_policy="auto_on_sign")
    assert r.status_code == 422, r.text
    assert "Nothing to attest" in r.json()["detail"]

    r2 = _create(country, promotion_policy="auto_on_sign", advance_review_status=True)
    assert r2.status_code == 201, r2.text
    items = r2.json()["request"]["items"]
    assert [i["title"] for i in items] == ["Tax card only"]
    assert items[0]["id"]  # snapshot contains the pending row, not an empty 422


# ── 3. Pre-feature create: client sends neither new key ────────────────────────
def test_a_legacy_shaped_create_still_defaults_to_manual_and_does_not_auto_publish():
    """Old clients omit promotion_policy. The server must default manual.

    Then a credentialed signature must behave as it did before ATT-2: recorded, not
    published, until an admin hits /promote.
    """
    country = f"ZOLD_{uuid.uuid4().hex[:8]}"
    _add_item(country, pillar="RESIDENCE", title="Police registration",
              desc="Register with the police.", review="approved")
    body = {"country_code": country, "purpose": "employment",
            "reviewer_org": "Advokatfirmaet Example AS", "reviewer_name": "Kari Nordmann",
            "reviewer_email": "kari@example.no"}
    assert "promotion_policy" not in body
    assert "advance_review_status" not in body
    r = client.post("/api/admin/attestations", json=body)
    assert r.status_code == 201, r.text
    req_id = r.json()["request"]["id"]
    with SessionLocal() as db:
        row = db.get(models.CorridorAttestationRequest, req_id)
        assert row.promotion_policy == "manual"
        assert row.advance_review_status is False

    token = r.json()["review_token"]
    assert client.post(f"/api/admin/attestations/{req_id}/send").status_code == 200
    view = _decide(token)
    assert _sign(token, view["content_hash"]).status_code == 200
    with SessionLocal() as db:
        item = db.query(models.RequirementItem).filter(
            models.RequirementItem.country_code == country).one()
        assert item.attestation_status is None
        assert item.review_status == "approved"


# ── 4. Two signatures: append-only table, _latest_signature, no second promote ─
def test_a_second_public_sign_is_refused_after_auto_on_sign_closes_the_request():
    """The public token leaves OPEN_STATUSES on first sign. A second POST must 404."""
    country = f"Z2SIG_{uuid.uuid4().hex[:8]}"
    _add_item(country, pillar="RESIDENCE", title="Police registration",
              desc="Register with the police.", review="approved")
    req_id, token = _open(country, promotion_policy="auto_on_sign")
    view = _decide(token)
    assert _sign(token, view["content_hash"]).status_code == 200
    r2 = _sign(token, view["content_hash"], signer_name="Second Signer")
    assert r2.status_code == 404, r2.text
    with SessionLocal() as db:
        n = db.query(models.CorridorAttestationSignature).filter(
            models.CorridorAttestationSignature.request_id == req_id).count()
    assert n == 1


def test_latest_signature_is_the_newest_row_and_does_not_re_promote():
    """The table is append-only. If a second row appears (re-issue / supersede), GET
    must show that row and requirement_items must not be touched again.
    """
    country = f"ZLATE_{uuid.uuid4().hex[:8]}"
    _add_item(country, pillar="RESIDENCE", title="Police registration",
              desc="Register with the police.", review="approved")
    req_id, token = _open(country, promotion_policy="auto_on_sign")
    view = _decide(token)
    assert _sign(token, view["content_hash"]).status_code == 200

    with SessionLocal() as db:
        first = _latest_signature(db, req_id)
        assert first is not None
        later = datetime.now(timezone.utc) + timedelta(seconds=5)
        db.add(models.CorridorAttestationSignature(
            id=str(uuid.uuid4()),
            request_id=req_id,
            signer_name="Later Counsel",
            signer_email="later@example.no",
            signer_org="Advokatfirmaet Example AS",
            signer_credential=CREDENTIAL,
            signature_method="typed_name",
            signed_content_hash=view["content_hash"],
            signed_payload_json={"reissue": True},
            disclaimer_version="v1",
            disclaimer_text="disclaimer",
            supersedes_signature_id=first.id,
            signed_at=later,
        ))
        db.commit()
        latest = _latest_signature(db, req_id)
        assert latest.signer_name == "Later Counsel"
        n = db.query(models.CorridorAttestationSignature).filter(
            models.CorridorAttestationSignature.request_id == req_id).count()
        assert n == 2
        item = db.query(models.RequirementItem).filter(
            models.RequirementItem.country_code == country).one()
        attested_by = item.attested_by

    shown = client.get(f"/api/public/attestations/{token}").json()
    assert shown["status"] == "signed"
    assert shown["signed_at"] is not None
    admin = client.get(f"/api/admin/attestations/{req_id}").json()
    assert admin["signature"]["signer_name"] == "Later Counsel"
    with SessionLocal() as db:
        item = db.query(models.RequirementItem).filter(
            models.RequirementItem.country_code == country).one()
        assert item.attestation_status == "attested"
        assert item.attested_by == attested_by
