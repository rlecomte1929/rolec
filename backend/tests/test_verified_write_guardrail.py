"""The verified-write guardrail: only a human can flip representative → expert_verified.

``verification_status`` is the provenance ladder (representative → corpus_grounded →
expert_verified, AIQ-1349), and its top rung is defined as a human signature. Before this
guardrail nothing enforced that: ``crud.create_requirement_item`` — the funnel every
automated producer uses (Otto promote, the YAML seeder, the research stub) — wrote whatever
``verification_status`` its payload carried. A seed file claiming ``expert_verified`` would
have recorded a lawyer sign-off that never happened, which is exactly the label-consistency
failure the provenance model exists to prevent.

Three things are pinned here, all fail-closed:

  (a) a generator/service write attempting to set ``expert_verified`` (or to smuggle the
      ``verified_by``/``verified_at`` signature columns, or to rewrite a human-verified
      row) is REJECTED — nothing written, nothing silently downgraded;
  (b) a human-actor write through ``mark_expert_verified`` / the admin verify endpoint
      succeeds and records ``verified_by`` + ``verified_at``;
  (c) the legitimate generator paths (representative / corpus_grounded, upsert semantics,
      the real YAML seeds) still pass unchanged.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import crud, models
from backend.app.services import verification_guard
from backend.app.services.verification_guard import (
    EXPERT_VERIFIED,
    VerificationWriteError,
    is_human_actor,
    mark_expert_verified,
)
from backend.scripts.seed_requirements import build_payloads


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", future=True)
    models.Base.metadata.create_all(engine, tables=[models.RequirementItem.__table__])
    with sessionmaker(bind=engine)() as session:
        yield session


def _payload(title: str, **over):
    base = dict(
        id=f"id-{title}",
        country_code="NORWAY",
        purpose="employment",
        pillar="RESIDENCE",
        title=title,
        description="…",
        severity="WARN",
        owner="EMPLOYEE",
        required_fields_json="[]",
        citations_json="[]",
        verification_status="corpus_grounded",
        last_verified_at=datetime(2026, 8, 19),
    )
    base.update(over)
    return base


# ── (a) the generator path is structurally unable to write the human signature ──────────


def test_generator_insert_cannot_set_expert_verified(db):
    with pytest.raises(VerificationWriteError):
        crud.create_requirement_item(db, _payload("Forged", verification_status=EXPERT_VERIFIED))
    assert db.query(models.RequirementItem).count() == 0  # nothing written


def test_generator_update_cannot_raise_a_row_to_expert_verified(db):
    crud.create_requirement_item(db, _payload("Escalated"))
    with pytest.raises(VerificationWriteError):
        crud.create_requirement_item(db, _payload("Escalated", verification_status=EXPERT_VERIFIED))
    row = db.query(models.RequirementItem).one()
    assert row.verification_status == "corpus_grounded"  # unchanged, not downgraded, not raised


def test_generator_cannot_smuggle_the_signature_columns(db):
    """verified_by/verified_at are guard-owned. A payload carrying them is a forgery attempt
    even when the status itself looks innocent."""
    with pytest.raises(VerificationWriteError):
        crud.create_requirement_item(
            db, _payload("Smuggled", verified_by="jane@relopass.com", verified_at=datetime.utcnow())
        )
    assert db.query(models.RequirementItem).count() == 0


def test_a_reseed_cannot_silently_downgrade_a_human_verified_row(db):
    """Reject, don't downgrade: once a human signed a row, an automated re-run that would
    rewrite its provenance fails loudly instead of quietly revoking the signature."""
    item = crud.create_requirement_item(db, _payload("Signed"))
    mark_expert_verified(item, verified_by="jane@relopass.com")
    db.commit()

    with pytest.raises(VerificationWriteError):
        crud.create_requirement_item(db, _payload("Signed", verification_status="representative"))
    db.rollback()
    row = db.query(models.RequirementItem).one()
    assert row.verification_status == EXPERT_VERIFIED
    assert row.verified_by == "jane@relopass.com"


def test_a_status_outside_the_canonical_ladder_is_rejected(db):
    """Label consistency: 'verified', 'draft' and other near-misses never enter the table."""
    for junk in ("verified", "draft", "lawyer_verified", "EXPERT_VERIFIED"):
        with pytest.raises(VerificationWriteError):
            crud.create_requirement_item(db, _payload(f"Junk {junk}", verification_status=junk))
    assert db.query(models.RequirementItem).count() == 0


def test_a_seed_file_claiming_expert_verified_fails_at_expansion():
    """The YAML seeder is an automated path; the claim dies in build_payloads, before any
    DB session opens — and would die again in crud if it somehow got past."""
    seed = {
        "verification_status": "expert_verified",
        "purposes_by_country": {"FRANCE": ["employment"]},
        "requirements": [{
            "key": "x", "pillar": "IDENTITY", "severity": "BLOCKER", "owner": "EMPLOYEE",
            "countries": {"FRANCE": {"title": "T", "description": "D."}},
        }],
    }
    with pytest.raises(VerificationWriteError):
        build_payloads(seed)


def test_mark_expert_verified_refuses_automated_identities(db):
    item = crud.create_requirement_item(db, _payload("Target"))
    for automated in (
        None,
        "",
        "   ",
        "otto-research",
        "service:catalog-promotion",
        "llm",
        "gpt-5",
        "seed_requirements script",
        "ci-pipeline",
        "renovate[bot]",
        "system",
    ):
        with pytest.raises(VerificationWriteError):
            mark_expert_verified(item, verified_by=automated)
    db.rollback()
    row = db.query(models.RequirementItem).one()
    assert row.verification_status == "corpus_grounded"
    assert row.verified_by is None and row.verified_at is None


def test_is_human_actor_token_matching_does_not_flag_substrings():
    # Deny-list matches whole identity tokens, not substrings: a human whose name merely
    # contains a token must not be locked out of signing.
    assert is_human_actor("agathe.morel@relopass.com")  # contains 'ag', not token 'agent'
    assert is_human_actor("admin-7f2c (Jane Doe)")
    assert not is_human_actor("promo-bot@relopass.com")
    assert not is_human_actor("otto")


# ── (b) a human-actor write succeeds and records verified_by + verified_at ──────────────


def test_human_sign_off_records_actor_and_timestamp(db):
    item = crud.create_requirement_item(db, _payload("Reviewed by counsel"))
    mark_expert_verified(item, verified_by="  jane@relopass.com ")
    db.commit()

    row = db.query(models.RequirementItem).one()
    assert row.verification_status == EXPERT_VERIFIED
    assert row.verified_by == "jane@relopass.com"
    assert row.verified_at is not None


def _admin_client(monkeypatch, session_factory, audit_calls):
    from backend.app.routers import admin as admin_router

    monkeypatch.setattr(admin_router, "SessionLocal", session_factory)
    monkeypatch.setattr(
        admin_router, "_audit_postgres", lambda **kw: audit_calls.append(kw)
    )
    app = FastAPI()
    app.include_router(admin_router.router)
    app.dependency_overrides[admin_router.require_admin] = lambda: {
        "id": "admin-7f2c",
        "email": "jane@relopass.com",
        "role": "ADMIN",
    }
    return TestClient(app)


@pytest.fixture()
def shared_db():
    """One in-memory DB reachable from both the test and the endpoint's own session."""
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine, tables=[models.RequirementItem.__table__])
    return sessionmaker(bind=engine)


def test_admin_verify_endpoint_flips_and_stamps(monkeypatch, shared_db):
    with shared_db() as session:
        crud.create_requirement_item(session, _payload("Endpoint target", country_code="NORWAY"))

    audit_calls: list = []
    client = _admin_client(monkeypatch, shared_db, audit_calls)
    resp = client.post("/api/admin/countries/NORWAY/requirements/id-Endpoint target/verify")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verificationStatus"] == EXPERT_VERIFIED
    assert body["verifiedBy"] == "admin-7f2c"
    assert body["verifiedAt"] is not None
    # The signature is persisted, and the act is audited with the actor.
    with shared_db() as session:
        row = session.query(models.RequirementItem).one()
        assert row.verification_status == EXPERT_VERIFIED
        assert row.verified_by == "admin-7f2c"
        assert row.verified_at is not None
    assert audit_calls and audit_calls[0]["new_value"]["verification_status"] == EXPERT_VERIFIED
    assert audit_calls[0]["new_value"]["verified_by"] == "admin-7f2c"


def test_admin_verify_endpoint_fails_closed_without_an_actor(monkeypatch, shared_db):
    """An authenticated principal with no usable identity cannot leave a signature."""
    with shared_db() as session:
        crud.create_requirement_item(session, _payload("No actor", country_code="NORWAY"))

    from backend.app.routers import admin as admin_router

    audit_calls: list = []
    client = _admin_client(monkeypatch, shared_db, audit_calls)
    client.app.dependency_overrides[admin_router.require_admin] = lambda: {}

    resp = client.post("/api/admin/countries/NORWAY/requirements/id-No actor/verify")
    assert resp.status_code == 422
    with shared_db() as session:
        row = session.query(models.RequirementItem).one()
        assert row.verification_status == "corpus_grounded"
        assert row.verified_by is None
    assert audit_calls == []


def test_admin_verify_endpoint_404s_on_wrong_country(monkeypatch, shared_db):
    with shared_db() as session:
        crud.create_requirement_item(session, _payload("Elsewhere", country_code="NORWAY"))
    client = _admin_client(monkeypatch, shared_db, [])
    resp = client.post("/api/admin/countries/FRANCE/requirements/id-Elsewhere/verify")
    assert resp.status_code == 404


# ── (c) legitimate promotion/seed paths still pass ──────────────────────────────────────


def test_generator_writable_statuses_still_flow(db):
    """representative and corpus_grounded — what Otto promote and the YAML seeds actually
    write — insert and update exactly as before."""
    crud.create_requirement_item(db, _payload("Legit", verification_status="representative"))
    row = db.query(models.RequirementItem).one()
    assert row.verification_status == "representative"

    crud.create_requirement_item(db, _payload("Legit", verification_status="corpus_grounded"))
    row = db.query(models.RequirementItem).one()
    assert row.verification_status == "corpus_grounded"


def test_a_payload_with_no_provenance_claim_still_flows(db):
    """The research stub writes items without verification_status; NULL stays legal."""
    p = _payload("No claim")
    p.pop("verification_status")
    crud.create_requirement_item(db, p)
    assert db.query(models.RequirementItem).one().verification_status is None


def test_every_committed_seed_file_still_expands():
    """The real YAML seeds only claim generator-writable provenance, so the guard
    must not reject any of them."""
    import glob
    import os

    import yaml

    seeds = glob.glob(
        os.path.join(os.path.dirname(__file__), "..", "seeds", "requirements", "*.yaml")
    )
    assert seeds, "seed files should exist"
    for path in seeds:
        with open(path, "r", encoding="utf-8") as fh:
            seed = yaml.safe_load(fh)
        payloads = build_payloads(seed)
        assert all(
            p["verification_status"] in verification_guard.GENERATOR_WRITABLE_STATUSES
            for p in payloads
        ), path


def test_otto_promotion_drafts_stay_generator_writable():
    """The Otto mapper's outputs (the real generator) pass the guard by construction —
    a change that makes it emit expert_verified must break here."""
    from types import SimpleNamespace

    from backend.imports.otto.mappings import resolve

    entity = SimpleNamespace(
        destination_country="FR",
        topic_key="eu_free_movement_worker",
        title="EU/EEA/Swiss citizen – worker right of residence",
        domain_area="immigration",
    )
    fact = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        fact_type="fee",
        fact_key="cardFee",
        fact_text="The card is free of charge.",
        applies_to={"role": "primary", "status": "professional", "nationality": "EU"},
        source_url="https://www.service-public.gouv.fr/particuliers/vosdroits/F16003",
        evidence_quote="délivrée gratuitement",
        accuracy_tier="auto_accepted",
    )
    draft = resolve(entity, [fact])
    verification_guard.assert_generator_verification_write(
        draft.payload, context="otto.promote"
    )  # must not raise
