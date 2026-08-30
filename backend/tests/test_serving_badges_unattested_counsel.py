"""A `needs_lawyer_review`-flagged, un-attested requirement is SERVED with a caveat badge.

Policy history on this row:
  * before 2026-08-30: served silently (approval-only gate; the serving path never re-checked).
  * #2131: WITHHELD from serving (matched the approval gate) — but that removed real, grounded,
    cited content from users.
  * now: SERVED again, with `legalReviewPending=True` in the response so the UI badges it "Legal
    review pending — not independently legal-reviewed." The founder chose the honest caveat over
    the blank, since no external counsel is engaged to attest it. Approval still blocks the same
    flag at `admin.py` — only the *serving* treatment changed from withhold to badge.

Discrimination is the point: `legal_review_pending` is True for the flagged-un-attested row and
False for a plain row and for an attested one; and `crud.list_requirements` no longer drops it.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import crud, models
from backend.app.services import lawyer_review_gate

CLEAN = "[]"
FLAGGED = json.dumps([{"needs_lawyer_review": True, "url": "https://www.example.gov"}])


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", future=True)
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    s = Session()
    yield s
    s.close()


def _row(title: str, citations: str, attestation_status):
    return models.RequirementItem(
        id=f"rq-{title}",
        country_code="FRANCE",
        purpose="employment",
        pillar="EMPLOYMENT",
        title=title,
        description="d",
        severity="WARN",
        owner="EMPLOYEE",
        required_fields_json="[]",
        citations_json=citations,
        review_status="approved",
        attestation_status=attestation_status,
        last_verified_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
    )


def _seed(db) -> None:
    db.add_all(
        [
            _row("plain", CLEAN, None),
            _row("counsel-unattested", FLAGGED, None),
            _row("counsel-attested", FLAGGED, "attested"),
        ]
    )
    db.commit()


def _titles(rows) -> set:
    return {r.title for r in rows}


def _pending(citations: str, attestation_status) -> bool:
    return lawyer_review_gate.legal_review_pending(
        attestation_status=attestation_status, blobs=(citations,)
    )


def test_the_badge_predicate_discriminates() -> None:
    assert _pending(FLAGGED, None) is True           # flagged + un-attested → badge
    assert _pending(FLAGGED, "attested") is False     # attested → no badge
    assert _pending(CLEAN, None) is False             # never flagged → no badge


def test_serving_no_longer_withholds_the_flagged_row(db) -> None:
    _seed(db)
    served = _titles(crud.list_requirements(db, "FRANCE", "employment"))
    # #2131 dropped it; the badge policy serves it again.
    assert served == {"plain", "counsel-unattested", "counsel-attested"}


def test_admin_review_surface_also_sees_all(db) -> None:
    _seed(db)
    admin = _titles(crud.list_requirements(db, "FRANCE", "employment", include_unapproved=True))
    assert admin == {"plain", "counsel-unattested", "counsel-attested"}


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
