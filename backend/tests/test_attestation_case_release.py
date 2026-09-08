"""[ATT-3.3] A case-scoped attestation, validly signed with advance_review_status, releases
the case roadmap to the employee — the case-level analogue of ATT-2.4's requirement-item
review advancement.

The positive property is the feature; the negatives are the safety: a corridor attestation
(no case) and an un-opted-in case attestation must release NOTHING, and a release failure must
never disturb the already-committed signature (fail-open).
"""
import os
import uuid

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402

from backend.app import models  # noqa: E402
from backend.app.db import SessionLocal, engine, Base  # noqa: E402
from backend.app.routers import attestation as att  # noqa: E402


@pytest.fixture(autouse=True)
def _tables():
    Base.metadata.create_all(bind=engine)
    yield


# ── _release_case_roadmap: the release helper ────────────────────────────────

def test_release_creates_the_row_when_absent():
    case_id = str(uuid.uuid4())
    with SessionLocal() as db:
        att._release_case_roadmap(db, case_id, actor="auto:Counsel", request_id="req-1")
    with SessionLocal() as db:
        row = db.get(models.RoadmapReviewStatus, case_id)
    assert row is not None and row.released_to_user is True
    assert row.reviewer_id == "auto:Counsel"
    assert "req-1" in (row.notes or "")


def test_release_flips_an_existing_unreleased_row():
    case_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(models.RoadmapReviewStatus(case_id=case_id, released_to_user=False))
        db.commit()
    with SessionLocal() as db:
        att._release_case_roadmap(db, case_id, actor="auto:C", request_id="r2")
    with SessionLocal() as db:
        assert db.get(models.RoadmapReviewStatus, case_id).released_to_user is True


def test_release_is_idempotent_and_does_not_overwrite_a_prior_releaser():
    """Already released → no-op. A case HR released must not be re-attributed to counsel."""
    case_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(models.RoadmapReviewStatus(
            case_id=case_id, released_to_user=True, reviewer_id="hr:jane"))
        db.commit()
    with SessionLocal() as db:
        att._release_case_roadmap(db, case_id, actor="auto:Counsel", request_id="r3")
    with SessionLocal() as db:
        row = db.get(models.RoadmapReviewStatus, case_id)
    assert row.released_to_user is True
    assert row.reviewer_id == "hr:jane"


def test_release_fails_open_on_a_broken_session():
    class _Boom:
        def get(self, *a, **k):
            raise RuntimeError("db down")

        def rollback(self):
            pass

    # Must not raise — the signature/promotion are already committed by the caller.
    att._release_case_roadmap(_Boom(), "case-x", actor="auto:C", request_id="r4")


# ── _maybe_auto_promote gating ───────────────────────────────────────────────

def _body(credential="NO-BAR-1"):
    return SimpleNamespace(signer_credential=credential, signer_name="Counsel")


def _req(case_id, advance):
    return SimpleNamespace(
        id="req-" + uuid.uuid4().hex[:6],
        promotion_policy="auto_on_sign",
        case_id=case_id,
        advance_review_status=advance,
    )


def test_case_scoped_opted_in_signature_releases_the_case(monkeypatch):
    monkeypatch.setattr(att, "_apply_promotion",
                        lambda db, req, **k: SimpleNamespace(promoted_count=1))
    case_id = str(uuid.uuid4())
    with SessionLocal() as db:
        att._maybe_auto_promote(db, _req(case_id, True), _body())
    with SessionLocal() as db:
        row = db.get(models.RoadmapReviewStatus, case_id)
    assert row is not None and row.released_to_user is True


def test_corridor_signature_releases_no_case(monkeypatch):
    monkeypatch.setattr(att, "_apply_promotion",
                        lambda db, req, **k: SimpleNamespace(promoted_count=1))
    calls = []
    monkeypatch.setattr(att, "_release_case_roadmap", lambda *a, **k: calls.append(1))
    with SessionLocal() as db:
        att._maybe_auto_promote(db, _req(None, True), _body())
    assert calls == []


def test_a_case_not_opted_into_advance_review_is_not_released(monkeypatch):
    monkeypatch.setattr(att, "_apply_promotion",
                        lambda db, req, **k: SimpleNamespace(promoted_count=1))
    calls = []
    monkeypatch.setattr(att, "_release_case_roadmap", lambda *a, **k: calls.append(1))
    with SessionLocal() as db:
        att._maybe_auto_promote(db, _req(str(uuid.uuid4()), False), _body())
    assert calls == []
