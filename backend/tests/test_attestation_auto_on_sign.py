"""AIQ-2106 [ATT-2.4] — auto_on_sign: a valid, credentialed signature publishes.

This is the file that documents a DELIBERATE waiver of the two-key rule. Its sibling,
test_attestation_endpoints.test_signing_alone_does_not_touch_requirement_items_on_the_manual_path,
asserts the opposite for the default path. Neither test means anything alone: together they
say "signing publishes ONLY when the request opted in at creation, and never otherwise".

The assertions that matter most are the negative ones — manual unchanged, uncredentialed
signer not promoted, hash mismatch not promoted. Auto-publishing is the feature; refusing
to auto-publish is the safety property.
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


@pytest.fixture
def corridor():
    """2 approved + 1 PENDING legal row. The pending row is what advance_review_status
    is supposed to publish, and the control that proves it did nothing when unset."""
    country = f"ZAUTO_{uuid.uuid4().hex[:8]}"
    rows = [
        ("RESIDENCE", "Police registration", "Register with the police.", "approved"),
        ("IDENTITY", "D-number", "Apply for a D-number.", "approved"),
        ("EMPLOYMENT", "Tax card (unpublished)", "Obtain a tax card.", "pending"),
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
            "reviewer_org": "Advokatfirmaet Example AS", "reviewer_name": "Kari Nordmann",
            "reviewer_email": "kari@example.no"}
    body.update(kw)
    r = client.post("/api/admin/attestations", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _open(country, **kw):
    created = _create(country, **kw)
    req_id, token = created["request"]["id"], created["review_token"]
    assert client.post(f"/api/admin/attestations/{req_id}/send").status_code == 200
    return req_id, token


def _decide(token, decision="approved"):
    view = client.get(f"/api/public/attestations/{token}").json()
    for item in view["items"]:
        r = client.post(f"/api/public/attestations/{token}/items/{item['id']}",
                        json={"decision": decision})
        assert r.status_code == 200, r.text
    return client.get(f"/api/public/attestations/{token}").json()


def _sign(token, content_hash, credential=CREDENTIAL):
    body = {"signer_name": "Kari Nordmann", "signer_email": "kari@example.no",
            "signer_org": "Advokatfirmaet Example AS",
            "content_hash": content_hash, "agreed_to_disclaimer": True}
    if credential is not None:
        body["signer_credential"] = credential
    return client.post(f"/api/public/attestations/{token}/sign", json=body)


def _items(ids):
    with SessionLocal() as db:
        return {r.title: r for r in db.query(models.RequirementItem).filter(
            models.RequirementItem.id.in_(list(ids.values()))).all()}


# ── the feature ────────────────────────────────────────────────────────────────
def test_auto_on_sign_attests_on_a_valid_credentialed_signature(corridor):
    req_id, token = _open(corridor["country"], promotion_policy="auto_on_sign")
    view = _decide(token)
    r = _sign(token, view["content_hash"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "signed"

    items = _items(corridor["ids"])
    assert items["Police registration"].attestation_status == "attested"
    assert items["D-number"].attestation_status == "attested"


def test_attested_by_is_the_firm_not_the_actor(corridor):
    """The ATT-2.3 design note, now load-bearing: who published != whose opinion it is."""
    req_id, token = _open(corridor["country"], promotion_policy="auto_on_sign")
    view = _decide(token)
    _sign(token, view["content_hash"])
    item = _items(corridor["ids"])["Police registration"]
    assert item.attested_by == "Advokatfirmaet Example AS"
    assert "auto:" not in (item.attested_by or "")


def test_advance_review_status_publishes_the_pending_row(corridor):
    """THE serving change. review_status='approved' is what requirements_builder serves."""
    req_id, token = _open(corridor["country"], promotion_policy="auto_on_sign",
                          advance_review_status=True)
    view = _decide(token)
    assert len(view["items"]) == 3, "advance_review_status should have widened the snapshot"
    assert _sign(token, view["content_hash"]).status_code == 200

    pending = _items(corridor["ids"])["Tax card (unpublished)"]
    assert pending.review_status == "approved"
    assert pending.attestation_status == "attested"
    assert pending.reviewed_by == "auto:Kari Nordmann"
    assert pending.reviewed_at is not None


def test_without_advance_review_status_the_pending_row_stays_unpublished(corridor):
    """The control. Auto-attesting must not silently publish anything."""
    req_id, token = _open(corridor["country"], promotion_policy="auto_on_sign")
    view = _decide(token)
    _sign(token, view["content_hash"])
    items = _items(corridor["ids"])
    assert items["Tax card (unpublished)"].review_status == "pending"
    assert items["Tax card (unpublished)"].attestation_status is None
    assert items["Police registration"].review_status == "approved"  # was already


# ── the refusals ───────────────────────────────────────────────────────────────
def test_manual_policy_still_requires_the_admin_key(corridor):
    """The default path is untouched — this is the two-key rule, still standing."""
    req_id, token = _open(corridor["country"])  # no policy => 'manual'
    view = _decide(token)
    assert _sign(token, view["content_hash"]).status_code == 200
    assert all(i.attestation_status is None for i in _items(corridor["ids"]).values())

    assert client.post(f"/api/admin/attestations/{req_id}/promote").status_code == 200
    assert _items(corridor["ids"])["Police registration"].attestation_status == "attested"


def test_an_uncredentialed_signer_is_recorded_but_does_not_publish(corridor):
    """An attestation is worth the signer's standing. No credential, no auto-publish —
    but the signature is still stored: refusing to publish is not refusing the review."""
    req_id, token = _open(corridor["country"], promotion_policy="auto_on_sign",
                          advance_review_status=True)
    view = _decide(token)
    r = _sign(token, view["content_hash"], credential=None)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "signed"

    with SessionLocal() as db:
        sigs = db.query(models.CorridorAttestationSignature).filter(
            models.CorridorAttestationSignature.request_id == req_id).all()
    assert len(sigs) == 1, "the signature must still be recorded"

    items = _items(corridor["ids"])
    assert all(i.attestation_status is None for i in items.values())
    assert items["Tax card (unpublished)"].review_status == "pending"


def test_a_blank_credential_is_treated_as_absent(corridor):
    req_id, token = _open(corridor["country"], promotion_policy="auto_on_sign")
    view = _decide(token)
    assert _sign(token, view["content_hash"], credential="   ").status_code == 200
    assert all(i.attestation_status is None for i in _items(corridor["ids"]).values())


def test_a_stale_content_hash_never_reaches_the_promotion(corridor):
    """The sign gate fires first, so nothing is signed AND nothing is published."""
    req_id, token = _open(corridor["country"], promotion_policy="auto_on_sign",
                          advance_review_status=True)
    _decide(token)
    r = _sign(token, "0" * 64)
    assert r.status_code == 409

    with SessionLocal() as db:
        assert db.query(models.CorridorAttestationSignature).filter(
            models.CorridorAttestationSignature.request_id == req_id).count() == 0
    items = _items(corridor["ids"])
    assert all(i.attestation_status is None for i in items.values())
    assert items["Tax card (unpublished)"].review_status == "pending"


def test_an_amended_item_is_not_published_even_on_auto(corridor):
    """approved-only selection is inside _apply_promotion and must survive the auto path."""
    req_id, token = _open(corridor["country"], promotion_policy="auto_on_sign",
                          advance_review_status=True)
    view = client.get(f"/api/public/attestations/{token}").json()
    by_title = {i["title"]: i for i in view["items"]}
    for title, item in by_title.items():
        decision = "amended" if title == "Tax card (unpublished)" else "approved"
        client.post(f"/api/public/attestations/{token}/items/{item['id']}",
                    json={"decision": decision, "proposed_amendment": "reword"})
    view = client.get(f"/api/public/attestations/{token}").json()
    assert _sign(token, view["content_hash"]).status_code == 200

    items = _items(corridor["ids"])
    assert items["Police registration"].attestation_status == "attested"
    # The amended row must be neither attested NOR published.
    assert items["Tax card (unpublished)"].attestation_status is None
    assert items["Tax card (unpublished)"].review_status == "pending"


def test_a_failed_promotion_keeps_the_signature_and_publishes_nothing(corridor, monkeypatch):
    """The reason the signature is committed before the promotion is attempted.

    _apply_promotion rolls back on its partial-write guard; inside one transaction that
    would destroy the signature, and the reviewer could not re-sign to recover it (status
    'signed' is not in OPEN_STATUSES, so the token 404s). Simulate any promotion failure
    and assert the conservative outcome: signature kept, nothing attested, nothing
    published, request left for an admin to promote manually.
    """
    import backend.app.routers.attestation as att

    req_id, token = _open(corridor["country"], promotion_policy="auto_on_sign",
                          advance_review_status=True)
    view = _decide(token)

    def _boom(*a, **kw):
        raise RuntimeError("simulated catalog inconsistency")

    monkeypatch.setattr(att, "_apply_promotion", _boom)
    r = _sign(token, view["content_hash"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "signed"

    with SessionLocal() as db:
        assert db.query(models.CorridorAttestationSignature).filter(
            models.CorridorAttestationSignature.request_id == req_id).count() == 1
    items = _items(corridor["ids"])
    assert all(i.attestation_status is None for i in items.values())
    assert items["Tax card (unpublished)"].review_status == "pending"

    # …and the manual key still works afterwards, once the cause is resolved.
    monkeypatch.undo()
    assert client.post(f"/api/admin/attestations/{req_id}/promote").status_code == 200
    assert _items(corridor["ids"])["Police registration"].attestation_status == "attested"
