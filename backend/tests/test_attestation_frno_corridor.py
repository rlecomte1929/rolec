"""Phase 5 — the FR→NO corridor walked end to end, with the real NORWAY item set.

Distinct from test_attestation_endpoints.py, which uses a synthetic 4-item fixture to probe
edge cases. This one uses the eight legal requirements that actually exist for NORWAY in
production (verified against the live catalog 2026-08-16), so it proves the flow against the
shape of real data — including that the two operational items are excluded by default.

Live NORWAY catalog at the time of writing: 11 approved rows, of which 10 are
verification_status='verified'. The two operational ones are HOUSING/'Long-term housing
contract' and TIMELINE/'Minimum lead time'. Every other row is a legal requirement and
belongs in counsel scope.
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
from backend.app.db import Base, SessionLocal, engine  # noqa: E402
from backend.main import app  # noqa: E402

client = TestClient(app)
ADMIN = {"id": "a1", "email": "romain@relopass.com", "is_admin": True, "role": "ADMIN"}

#: The real NORWAY rows. (pillar, title, legal?)
NORWAY_CATALOG = [
    ("EMPLOYMENT", "Employment letter", True),
    ("EMPLOYMENT", "Tax deduction card (skattekort) before first salary", True),
    ("IDENTITY", "D-number (stays under 6 months)", True),
    ("IDENTITY", "Valid identity card or passport (EU/EEA)", True),
    ("IDENTITY", "Valid passport (6+ months)", True),
    ("RESIDENCE", "Police registration for EU/EEA nationals (stays over 3 months)", True),
    ("RESIDENCE", "Residence registration (folkeregister)", True),
    ("SOCIAL_SECURITY", "A1 certificate for genuinely posted workers", True),
    ("SOCIAL_SECURITY", "National Insurance registration (folketrygden)", True),
    ("HOUSING", "Long-term housing contract", False),      # operational
    ("TIMELINE", "Minimum lead time", False),              # operational
]

LEGAL_COUNT = sum(1 for _, _, legal in NORWAY_CATALOG if legal)


@pytest.fixture(autouse=True)
def _setup():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[require_admin] = lambda: ADMIN
    yield
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def norway():
    """Seed the real NORWAY set, plus a FRANCE corridor as the untouched control."""
    suffix = uuid.uuid4().hex[:8]
    no_key, fr_key = f"NORWAY_{suffix}", f"FRANCE_{suffix}"
    legal_ids, operational_ids, france_ids = [], [], []

    with SessionLocal() as db:
        for pillar, title, is_legal in NORWAY_CATALOG:
            rid = str(uuid.uuid4())
            db.add(models.RequirementItem(
                id=rid, country_code=no_key, purpose="employment", pillar=pillar,
                title=title, description=f"{title} — indicative; confirm with the authority.",
                severity="WARN", owner="EMPLOYEE", required_fields_json="[]",
                citations_json='[{"url": "https://www.skatteetaten.no/en/example"}]',
                verification_status="verified", review_status="approved",
                last_verified_at=datetime.utcnow(),
            ))
            (legal_ids if is_legal else operational_ids).append(rid)

        for title in ["Long-stay visa (VLS-TS)", "OFII validation"]:
            rid = str(uuid.uuid4())
            db.add(models.RequirementItem(
                id=rid, country_code=fr_key, purpose="employment", pillar="RESIDENCE",
                title=title, description=title, severity="WARN", owner="EMPLOYEE",
                required_fields_json="[]", citations_json="[]",
                verification_status="verified", review_status="approved",
                last_verified_at=datetime.utcnow(),
            ))
            france_ids.append(rid)
        db.commit()

    return {"no": no_key, "fr": fr_key, "legal": legal_ids,
            "operational": operational_ids, "france": france_ids}


def _states(ids):
    with SessionLocal() as db:
        return {
            r.id: (r.attestation_status, r.attested_by, r.verification_status)
            for r in db.query(models.RequirementItem).filter(models.RequirementItem.id.in_(ids)).all()
        }


def test_frno_full_walkthrough_signature_hash_and_promoted_rows(norway):
    """Create → send → review → sign → promote, and prove FRANCE is untouched throughout."""
    # ── create: default scope must pick the 9 legal items and drop the 2 operational
    created = client.post("/api/admin/attestations", json={
        "country_code": norway["no"], "purpose": "employment",
        "title": "France → Norway — legal compliance attestation",
        "reviewer_org": "Advokatfirmaet Example AS", "reviewer_name": "Kari Nordmann",
        "reviewer_email": "kari@example.no", "reviewer_credential": "NO-BAR-1234",
    }).json()
    req_id, token = created["request"]["id"], created["review_token"]

    assert created["request"]["item_count"] == LEGAL_COUNT == 9
    titles = {i["title"] for i in created["request"]["items"]}
    assert "Tax deduction card (skattekort) before first salary" in titles
    assert "National Insurance registration (folketrygden)" in titles
    assert "A1 certificate for genuinely posted workers" in titles
    assert "Long-term housing contract" not in titles   # operational, correctly excluded
    assert "Minimum lead time" not in titles

    snapshot_hash = created["request"]["content_snapshot_hash"]
    assert len(snapshot_hash) == 64

    # ── send, then the reviewer opens the link
    client.post(f"/api/admin/attestations/{req_id}/send")
    view = client.get(f"/api/public/attestations/{token}").json()
    assert len(view["items"]) == 9
    assert view["content_hash"] == snapshot_hash

    # ── counsel approves 8, requests a change on the skattekort wording
    for item in view["items"]:
        if item["title"].startswith("Tax deduction card"):
            body = {"decision": "amended",
                    "reviewer_comment": "Deadline should reference the first payment of salary, not arrival.",
                    "proposed_amendment": "Obtain a skattekort before your first salary payment."}
        else:
            body = {"decision": "approved"}
        view = client.post(f"/api/public/attestations/{token}/items/{item['id']}", json=body).json()

    assert view["status"] == "changes_requested"

    # ── nothing served has changed yet: signing has not even happened
    assert all(v[0] is None for v in _states(norway["legal"]).values())

    # ── sign
    signed = client.post(f"/api/public/attestations/{token}/sign", json={
        "signer_name": "Kari Nordmann", "signer_email": "kari@example.no",
        "signer_org": "Advokatfirmaet Example AS", "signer_credential": "NO-BAR-1234",
        "signature_method": "typed_name", "content_hash": view["content_hash"],
        "agreed_to_disclaimer": True,
    })
    assert signed.status_code == 200, signed.text

    with SessionLocal() as db:
        sig = db.query(models.CorridorAttestationSignature).filter_by(request_id=req_id).one()
        assert sig.signed_content_hash == snapshot_hash
        assert sig.signer_credential == "NO-BAR-1234"
        assert sig.disclaimer_version == "v1"
        assert len(sig.signed_payload_json["decisions"]) == 9
        amended = [d for d in sig.signed_payload_json["decisions"] if d["decision"] == "amended"]
        assert len(amended) == 1
        # Both the reviewer's reasoning and their proposed wording are frozen into the
        # signature — an amendment whose rationale was dropped is not reviewable later.
        assert "first payment of salary" in amended[0]["reviewer_comment"]
        assert "first salary payment" in amended[0]["proposed_amendment"]

    # STILL nothing served has changed — the signature alone promotes nothing.
    assert all(v[0] is None for v in _states(norway["legal"]).values())

    # ── promote (the second key)
    result = client.post(f"/api/admin/attestations/{req_id}/promote").json()
    assert result["promoted_count"] == 8            # the amended item is NOT promoted
    assert len(result["skipped_not_approved"]) == 1
    assert result["attested_by"] == "Advokatfirmaet Example AS"

    states = _states(norway["legal"])
    attested = [i for i, v in states.items() if v[0] == "attested"]
    assert len(attested) == 8
    assert all(v[1] == "Advokatfirmaet Example AS" for i, v in states.items() if v[0] == "attested")
    # The orthogonal axis is untouched — attesting must not launder a claim up the other ladder.
    assert all(v[2] == "verified" for v in states.values())

    with SessionLocal() as db:
        row = db.query(models.RequirementItem).filter(
            models.RequirementItem.id == attested[0]).one()
        assert row.attested_at is not None
        assert row.latest_attestation_request_id == req_id

    # ── the other corridor is untouched, which is the containment claim
    assert all(v[0] is None for v in _states(norway["france"]).values())
    # …and so are NORWAY's operational items, which were never in scope.
    assert all(v[0] is None for v in _states(norway["operational"]).values())


def test_sellable_means_both_axes(norway):
    """`verified` alone is not sellable; `attested` alone is not either. Pin the conjunction."""
    created = client.post("/api/admin/attestations", json={
        "country_code": norway["no"], "reviewer_org": "Example AS"}).json()
    req_id, token = created["request"]["id"], created["review_token"]
    client.post(f"/api/admin/attestations/{req_id}/send")
    view = client.get(f"/api/public/attestations/{token}").json()
    for item in view["items"]:
        view = client.post(f"/api/public/attestations/{token}/items/{item['id']}",
                           json={"decision": "approved"}).json()
    client.post(f"/api/public/attestations/{token}/sign", json={
        "signer_name": "K", "signer_email": "k@example.no", "signer_org": "Example AS",
        "content_hash": view["content_hash"], "agreed_to_disclaimer": True})
    client.post(f"/api/admin/attestations/{req_id}/promote")

    with SessionLocal() as db:
        sellable = db.query(models.RequirementItem).filter(
            models.RequirementItem.country_code == norway["no"],
            models.RequirementItem.verification_status == "verified",
            models.RequirementItem.attestation_status == "attested",
        ).all()
        # The 9 legal items are both verified and attested. The 2 operational ones are
        # verified but were never in counsel scope, so they are not sellable.
        assert len(sellable) == 9
        not_attested = db.query(models.RequirementItem).filter(
            models.RequirementItem.country_code == norway["no"],
            models.RequirementItem.attestation_status.is_(None),
        ).count()
        assert not_attested == 2
