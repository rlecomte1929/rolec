"""Counsel attestation — admin + tokenized public endpoints, end to end.

App is mounted from `backend.main` (the entrypoint uvicorn actually boots) so these tests
also prove the routes reached the PROD registration, not just the modular app. Auth is
overridden on `backend.app.auth_deps.require_admin` — the reference the router imports.
Overriding the same-named function in `backend.main` silently never fires (CLAUDE.md).

The six guarantees Phase 4 asks for, each with its own test:
  happy path · expired/unknown → 404 · hash mismatch → 409 · PII boundary ·
  signature immutability · two-key separation.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

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
    """Seed a small NORWAY corridor: 3 legal items + 1 operational (HOUSING).

    The HOUSING row is the control for default scoping — it must be excluded unless the
    admin names it explicitly.
    """
    key = uuid.uuid4().hex[:8]
    country = f"NORWAY_{key}"
    rows = [
        ("EMPLOYMENT", "Tax deduction card (skattekort)", "Obtain a skattekort before first salary."),
        ("IDENTITY", "D-number", "Apply for a D-number for stays under 6 months."),
        ("RESIDENCE", "Police registration", "Register with the police within 3 months."),
        ("HOUSING", "Long-term housing contract", "Secure a long-term housing contract."),
    ]
    ids = []
    with SessionLocal() as db:
        for pillar, title, desc in rows:
            rid = str(uuid.uuid4())
            db.add(models.RequirementItem(
                id=rid, country_code=country, purpose="employment", pillar=pillar,
                title=title, description=desc, severity="WARN", owner="EMPLOYEE",
                required_fields_json="[]",
                citations_json='[{"url": "https://www.skatteetaten.no/en/example"}]',
                verification_status="verified", review_status="approved",
                last_verified_at=datetime.utcnow(),
            ))
            ids.append(rid)
        db.commit()
    return {"country": country, "ids": ids, "legal_ids": ids[:3], "housing_id": ids[3]}


def _create(country, **kw):
    body = {"country_code": country, "purpose": "employment",
            "reviewer_org": "Advokatfirmaet Example AS", "reviewer_name": "Kari Nordmann",
            "reviewer_email": "kari@example.no", "reviewer_credential": "NO-BAR-1234"}
    body.update(kw)
    r = client.post("/api/admin/attestations", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _send(request_id):
    r = client.post(f"/api/admin/attestations/{request_id}/send")
    assert r.status_code == 200, r.text
    return r.json()


def _decide_all(token, view, decision="approved"):
    for item in view["items"]:
        r = client.post(f"/api/public/attestations/{token}/items/{item['id']}",
                        json={"decision": decision})
        assert r.status_code == 200, r.text
        view = r.json()
    return view


# ── happy path ───────────────────────────────────────────────────────────────────────

def test_happy_path_create_view_decide_sign(corridor):
    created = _create(corridor["country"])
    token = created["review_token"]
    req_id = created["request"]["id"]

    # The raw token is returned once, and is NOT the stored hash.
    assert token and len(token) >= 32
    assert created["review_url"].endswith(f"/attest/{token}")

    # Default scoping drops the operational HOUSING item.
    assert created["request"]["item_count"] == 3
    titles = {i["title"] for i in created["request"]["items"]}
    assert "Long-term housing contract" not in titles

    # Not live until sent.
    assert client.get(f"/api/public/attestations/{token}").status_code == 404
    _send(req_id)

    view = client.get(f"/api/public/attestations/{token}").json()
    assert view["corridor_label"] == corridor["country"]
    assert len(view["items"]) == 3
    assert all(i["decision"] == "pending" for i in view["items"])
    assert view["disclaimer_version"] == "v1"
    assert "not legal advice in respect of any individual" in view["disclaimer_text"]

    view = _decide_all(token, view)
    assert view["status"] == "in_review"

    signed = client.post(f"/api/public/attestations/{token}/sign", json={
        "signer_name": "Kari Nordmann", "signer_email": "kari@example.no",
        "signer_org": "Advokatfirmaet Example AS", "signer_credential": "NO-BAR-1234",
        "signature_method": "typed_name", "content_hash": view["content_hash"],
        "agreed_to_disclaimer": True,
    })
    assert signed.status_code == 200, signed.text
    assert signed.json()["status"] == "signed"

    with SessionLocal() as db:
        sig = db.query(models.CorridorAttestationSignature).filter_by(request_id=req_id).one()
        req = db.get(models.CorridorAttestationRequest, req_id)
        assert sig.signed_content_hash == req.content_snapshot_hash
        assert sig.disclaimer_text and sig.disclaimer_version == "v1"
        assert len(sig.signed_payload_json["decisions"]) == 3
        # Only the hash is stored — never the raw token.
        assert req.link_token_hash != token
        assert token not in (req.link_token_hash or "")


def test_explicit_item_ids_are_not_silently_trimmed(corridor):
    """An explicit scope is a deliberate decision — including an operational pillar."""
    created = _create(corridor["country"], requirement_item_ids=corridor["ids"])
    assert created["request"]["item_count"] == 4


# ── 404: unknown / expired / malformed ───────────────────────────────────────────────

@pytest.mark.parametrize("bad", [
    "a" * 43,                                   # well-formed but unknown
    "unknown-token-that-does-not-exist-000000000",
    "short",                                    # fails the shape check before any query
    "'; DROP TABLE corridor_attestation_requests;--",
])
def test_unknown_or_malformed_tokens_are_404(bad):
    """Every miss returns the same 404 body — an attacker learns nothing from the difference.

    Path-traversal strings are deliberately NOT in this list: Starlette normalises
    `/api/public/attestations/../../etc/passwd` before routing, so it never reaches the
    handler and comes back 405 from the router. That is safe but it is a different code
    path, and asserting 404 on it would be testing Starlette. Traversal input is covered
    against `is_well_formed` directly in test_attestation_tokens.py.
    """
    r = client.get(f"/api/public/attestations/{bad}")
    assert r.status_code == 404
    assert r.json()["detail"] == "Attestation link not found or no longer valid."


def test_expired_token_is_404_not_403(corridor):
    """404 and not 403: a 403 confirms the token exists, which is an enumeration oracle."""
    created = _create(corridor["country"])
    token, req_id = created["review_token"], created["request"]["id"]
    _send(req_id)
    assert client.get(f"/api/public/attestations/{token}").status_code == 200

    with SessionLocal() as db:
        req = db.get(models.CorridorAttestationRequest, req_id)
        req.token_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    r = client.get(f"/api/public/attestations/{token}")
    assert r.status_code == 404
    # Byte-identical to the unknown-token body — no distinguishing signal.
    assert r.json()["detail"] == "Attestation link not found or no longer valid."


def test_expired_token_cannot_sign_either(corridor):
    created = _create(corridor["country"])
    token, req_id = created["review_token"], created["request"]["id"]
    _send(req_id)
    view = _decide_all(token, client.get(f"/api/public/attestations/{token}").json())

    with SessionLocal() as db:
        req = db.get(models.CorridorAttestationRequest, req_id)
        req.token_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()

    r = client.post(f"/api/public/attestations/{token}/sign", json={
        "signer_name": "K", "signer_email": "k@example.no",
        "content_hash": view["content_hash"], "agreed_to_disclaimer": True,
    })
    assert r.status_code == 404


# ── 409: content hash mismatch ───────────────────────────────────────────────────────

def test_sign_with_stale_content_hash_is_409(corridor):
    """The checklist moved under the reviewer — they must not sign what they never saw."""
    created = _create(corridor["country"])
    token, req_id = created["review_token"], created["request"]["id"]
    _send(req_id)
    view = _decide_all(token, client.get(f"/api/public/attestations/{token}").json())
    stale_hash = view["content_hash"]

    with SessionLocal() as db:
        req = db.get(models.CorridorAttestationRequest, req_id)
        req.content_snapshot_hash = "f" * 64          # simulate a re-snapshot after send
        db.commit()

    r = client.post(f"/api/public/attestations/{token}/sign", json={
        "signer_name": "Kari", "signer_email": "kari@example.no",
        "content_hash": stale_hash, "agreed_to_disclaimer": True,
    })
    assert r.status_code == 409
    assert "changed" in r.json()["detail"].lower()

    with SessionLocal() as db:
        assert db.query(models.CorridorAttestationSignature).filter_by(request_id=req_id).count() == 0


def test_sign_requires_every_item_decided(corridor):
    created = _create(corridor["country"])
    token, req_id = created["review_token"], created["request"]["id"]
    _send(req_id)
    view = client.get(f"/api/public/attestations/{token}").json()
    # decide only the first
    client.post(f"/api/public/attestations/{token}/items/{view['items'][0]['id']}",
                json={"decision": "approved"})
    r = client.post(f"/api/public/attestations/{token}/sign", json={
        "signer_name": "K", "signer_email": "k@example.no",
        "content_hash": view["content_hash"], "agreed_to_disclaimer": True,
    })
    assert r.status_code == 422 and "pending" in r.text.lower()


def test_sign_requires_explicit_disclaimer_agreement(corridor):
    created = _create(corridor["country"])
    token, req_id = created["review_token"], created["request"]["id"]
    _send(req_id)
    view = _decide_all(token, client.get(f"/api/public/attestations/{token}").json())
    r = client.post(f"/api/public/attestations/{token}/sign", json={
        "signer_name": "K", "signer_email": "k@example.no",
        "content_hash": view["content_hash"], "agreed_to_disclaimer": False,
    })
    assert r.status_code == 422


# ── PII boundary ─────────────────────────────────────────────────────────────────────

def test_public_payload_carries_no_case_employee_or_company_fields(corridor):
    """The reviewer is an external third party. Nothing personal may reach them."""
    created = _create(corridor["country"])
    token, req_id = created["review_token"], created["request"]["id"]
    _send(req_id)

    body = client.get(f"/api/public/attestations/{token}").text.lower()
    for forbidden in (
        "case_id", "caseid", "employee", "company_id", "companyid", "passport",
        "full_name", "fullname", "draft_json", "user_id", "reporter",
        "statusforcase", "date_of_birth", "nationality",
        # the reviewer's own contact details are admin-side data and must not echo back
        "kari@example.no", "reviewer_email", "requested_by", "admin@relopass.com",
    ):
        assert forbidden not in body, f"'{forbidden}' leaked into the public payload"


def test_public_response_keys_are_exactly_the_whitelist(corridor):
    created = _create(corridor["country"])
    token = created["review_token"]
    _send(created["request"]["id"])
    view = client.get(f"/api/public/attestations/{token}").json()

    assert set(view.keys()) == {
        "corridor_label", "purpose", "scope", "status", "title", "disclaimer_version",
        "disclaimer_text", "content_hash", "expires_at", "items", "signed_at",
    }
    assert set(view["items"][0].keys()) == {
        "id", "title", "claim", "source_url", "evidence", "pillar", "validity",
        "confidence", "decision", "reviewer_comment", "proposed_amendment",
    }


# ── two-key separation ───────────────────────────────────────────────────────────────

def _attestation_state(item_ids):
    with SessionLocal() as db:
        return {
            r.id: (r.attestation_status, r.attested_by, r.latest_attestation_request_id)
            for r in db.query(models.RequirementItem).filter(models.RequirementItem.id.in_(item_ids)).all()
        }


def test_signing_alone_does_not_touch_requirement_items(corridor):
    """THE two-key guarantee: a reviewer records an opinion, never a served claim."""
    before = _attestation_state(corridor["ids"])
    created = _create(corridor["country"])
    token, req_id = created["review_token"], created["request"]["id"]
    _send(req_id)
    view = _decide_all(token, client.get(f"/api/public/attestations/{token}").json())
    r = client.post(f"/api/public/attestations/{token}/sign", json={
        "signer_name": "Kari", "signer_email": "kari@example.no",
        "signer_org": "Advokatfirmaet Example AS",
        "content_hash": view["content_hash"], "agreed_to_disclaimer": True,
    })
    assert r.status_code == 200

    assert _attestation_state(corridor["ids"]) == before
    assert all(v[0] is None for v in _attestation_state(corridor["ids"]).values())


def test_promote_is_the_only_path_that_writes_attested(corridor):
    created = _create(corridor["country"])
    token, req_id = created["review_token"], created["request"]["id"]
    _send(req_id)
    view = _decide_all(token, client.get(f"/api/public/attestations/{token}").json())
    client.post(f"/api/public/attestations/{token}/sign", json={
        "signer_name": "Kari", "signer_email": "kari@example.no",
        "signer_org": "Advokatfirmaet Example AS",
        "content_hash": view["content_hash"], "agreed_to_disclaimer": True,
    })

    r = client.post(f"/api/admin/attestations/{req_id}/promote")
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["promoted_count"] == 3
    assert result["attested_by"] == "Advokatfirmaet Example AS"

    state = _attestation_state(corridor["legal_ids"])
    assert all(v[0] == "attested" for v in state.values())
    assert all(v[2] == req_id for v in state.values())
    # The operational item was never in scope and stays untouched.
    assert _attestation_state([corridor["housing_id"]])[corridor["housing_id"]][0] is None


def test_promote_refuses_an_unsigned_request(corridor):
    created = _create(corridor["country"])
    req_id = created["request"]["id"]
    _send(req_id)
    r = client.post(f"/api/admin/attestations/{req_id}/promote")
    assert r.status_code == 409
    assert all(v[0] is None for v in _attestation_state(corridor["ids"]).values())


def test_promote_refuses_when_the_checklist_moved_after_signing(corridor):
    created = _create(corridor["country"])
    token, req_id = created["review_token"], created["request"]["id"]
    _send(req_id)
    view = _decide_all(token, client.get(f"/api/public/attestations/{token}").json())
    client.post(f"/api/public/attestations/{token}/sign", json={
        "signer_name": "K", "signer_email": "k@example.no",
        "content_hash": view["content_hash"], "agreed_to_disclaimer": True,
    })
    with SessionLocal() as db:
        db.get(models.CorridorAttestationRequest, req_id).content_snapshot_hash = "e" * 64
        db.commit()

    r = client.post(f"/api/admin/attestations/{req_id}/promote")
    assert r.status_code == 409
    assert all(v[0] is None for v in _attestation_state(corridor["ids"]).values())


def test_promote_skips_items_the_reviewer_did_not_approve(corridor):
    created = _create(corridor["country"])
    token, req_id = created["review_token"], created["request"]["id"]
    _send(req_id)
    view = client.get(f"/api/public/attestations/{token}").json()
    decisions = ["approved", "rejected", "amended"]
    for item, decision in zip(view["items"], decisions):
        client.post(f"/api/public/attestations/{token}/items/{item['id']}",
                    json={"decision": decision, "reviewer_comment": "see note"})
    view = client.get(f"/api/public/attestations/{token}").json()
    assert view["status"] == "changes_requested"
    client.post(f"/api/public/attestations/{token}/sign", json={
        "signer_name": "K", "signer_email": "k@example.no",
        "content_hash": view["content_hash"], "agreed_to_disclaimer": True,
    })

    result = client.post(f"/api/admin/attestations/{req_id}/promote").json()
    assert result["promoted_count"] == 1
    assert len(result["skipped_not_approved"]) == 2

    attested = [i for i, v in _attestation_state(corridor["ids"]).items() if v[0] == "attested"]
    assert len(attested) == 1


def test_promote_never_touches_verification_status(corridor):
    """The two axes are orthogonal — attesting must not launder a claim up the other ladder."""
    created = _create(corridor["country"])
    token, req_id = created["review_token"], created["request"]["id"]
    _send(req_id)
    view = _decide_all(token, client.get(f"/api/public/attestations/{token}").json())
    client.post(f"/api/public/attestations/{token}/sign", json={
        "signer_name": "K", "signer_email": "k@example.no",
        "content_hash": view["content_hash"], "agreed_to_disclaimer": True,
    })
    client.post(f"/api/admin/attestations/{req_id}/promote")

    with SessionLocal() as db:
        rows = db.query(models.RequirementItem).filter(
            models.RequirementItem.id.in_(corridor["ids"])).all()
        assert all(r.verification_status == "verified" for r in rows)


def test_a_reviewer_cannot_decide_an_item_from_another_request(corridor):
    """The token authorises ONE envelope, not the items table."""
    a = _create(corridor["country"])
    b = _create(corridor["country"])
    _send(a["request"]["id"])
    _send(b["request"]["id"])
    b_item_id = client.get(f"/api/public/attestations/{b['review_token']}").json()["items"][0]["id"]

    r = client.post(f"/api/public/attestations/{a['review_token']}/items/{b_item_id}",
                    json={"decision": "approved"})
    assert r.status_code == 404


# ── admin authorization ──────────────────────────────────────────────────────────────

def test_admin_endpoints_reject_a_non_admin(corridor):
    app.dependency_overrides.pop(require_admin, None)
    try:
        cases = [
            ("post", "/api/admin/attestations", {"country_code": "NORWAY"}),
            ("get", "/api/admin/attestations", None),
            ("get", f"/api/admin/attestations/{uuid.uuid4()}", None),
            ("post", f"/api/admin/attestations/{uuid.uuid4()}/send", None),
            ("post", f"/api/admin/attestations/{uuid.uuid4()}/promote", None),
        ]
        for method, path, payload in cases:
            r = client.post(path, json=payload) if method == "post" else client.get(path)
            assert r.status_code in (401, 403), f"{method.upper()} {path} returned {r.status_code}"
    finally:
        app.dependency_overrides[require_admin] = lambda: ADMIN


# ── immutability ─────────────────────────────────────────────────────────────────────

def test_no_code_path_updates_or_deletes_a_signature():
    """Static guard: signatures are insert-only, so revocation is a NEW superseding row.

    A grep rather than a behavioural test on purpose — the guarantee is 'no such code
    exists', which no amount of endpoint exercising can demonstrate.
    """
    import pathlib
    src = pathlib.Path(__file__).resolve().parents[1]
    offenders = []
    for path in src.rglob("*.py"):
        if "test" in path.name:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "CorridorAttestationSignature" not in text:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            low = line.lower()
            if "corridorattestationsignature" in low and (".delete(" in low or ".update(" in low):
                offenders.append(f"{path.relative_to(src)}:{lineno}: {line.strip()}")
    assert not offenders, "signature rows must be insert-only:\n" + "\n".join(offenders)


# ── Postgres-shape regression ────────────────────────────────────────────────────────

def test_multiple_items_insert_in_one_flush(corridor):
    """A corridor with >1 item must create in a single request.

    The regression this pins: `id`/`request_id` are `uuid` in Postgres but were declared
    `Column(String)`, and `created_at` carries a server_default. That combination makes
    SQLAlchemy use RETURNING for the multi-row INSERT and then match result rows back to
    parameter sets by sentinel — which fails on Postgres with

        InvalidRequestError: Can't match sentinel values in result set to parameter sets

    SQLite has no real uuid type, so the whole suite stayed green while the FIRST live
    Postgres call 500'd. Fixed by `_UUID = Uuid(as_uuid=False)` plus
    `implicit_returning=False` on the three attestation tables.

    This test cannot fail on SQLite for the original reason — it is a shape guard, and the
    real proof was a live run against production Postgres (25/25). Kept so the intent is
    recorded next to the code and a future single-row rewrite does not look harmless.
    """
    created = _create(corridor["country"])
    assert created["request"]["item_count"] == 3, "multi-item insert must survive one flush"

    with SessionLocal() as db:
        rows = db.query(models.CorridorAttestationItem).filter_by(
            request_id=created["request"]["id"]).all()
        assert len(rows) == 3
        assert all(r.id and r.request_id for r in rows)
        # ids must be distinct — sentinel confusion would collapse or misassign them
        assert len({r.id for r in rows}) == 3


def test_attestation_tables_disable_implicit_returning():
    """Static guard on the fix itself, since the behavioural one can't fail on SQLite."""
    for model in (models.CorridorAttestationRequest,
                  models.CorridorAttestationItem,
                  models.CorridorAttestationSignature):
        assert model.__table__.implicit_returning is False, (
            f"{model.__tablename__} re-enabled implicit_returning — multi-row INSERT will "
            "fail on Postgres with a sentinel-matching error"
        )
