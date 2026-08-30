"""The serving path must withhold `needs_lawyer_review`-flagged, un-attested requirements.

Before this gate, the flag was checked only at *approval* (`admin.py`, via
`lawyer_review_gate.blocks_approval`). The serving read (`crud.list_requirements`) did not
re-check it, so 15 requirements approved BEFORE that gate existed kept serving unattested
(scan 2026-08-30: 3 FRANCE + 12 IRELAND). This asserts the second withhold added to
`list_requirements` — the same rule, now on the serving seam every reader shares.

Discrimination is the point: a *plain* approved row and an *attested* flagged row both still
serve; only the *flagged + un-attested* row is held back — and the admin review surface
(`include_unapproved=True`) still sees it so counsel can be requested and it can be attested.
Run against the pre-fix `list_requirements` and `test_serving_withholds_the_flagged_unattested`
FAILS (the row leaks), which is what makes this a gate and not decoration.
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


def test_the_flag_blob_actually_trips_the_gate() -> None:
    # If the shape stops being detected, every assertion below is vacuously green.
    assert lawyer_review_gate.carries_lawyer_review_flag(FLAGGED)
    assert not lawyer_review_gate.carries_lawyer_review_flag(CLEAN)


def test_serving_withholds_the_flagged_unattested(db) -> None:
    _seed(db)
    served = _titles(crud.list_requirements(db, "FRANCE", "employment"))
    assert "counsel-unattested" not in served, "un-attested counsel fact leaked to the serving path"
    assert served == {"plain", "counsel-attested"}


def test_the_admin_review_surface_still_sees_it(db) -> None:
    _seed(db)
    admin = _titles(crud.list_requirements(db, "FRANCE", "employment", include_unapproved=True))
    assert admin == {"plain", "counsel-unattested", "counsel-attested"}, "admin can no longer attest it"


def test_attestation_lifts_the_withhold(db) -> None:
    _seed(db)
    served = _titles(crud.list_requirements(db, "FRANCE", "employment"))
    assert "counsel-attested" in served, "an attested counsel row must serve"


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
