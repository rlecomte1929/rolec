"""`crud.create_requirement_item` must never replace a curated citation with nothing.

WHAT HAPPENED (2026-08-20)

`20261112000000` gave eight served requirements a verified official citation. Hours later
the guard went red: SINGAPORE "Valid passport (6+ months)" was back to `[]`, its
`last_verified_at` bumped.

The chain:

  backend/main.py `_run_background_startup_seed`   — runs on EVERY backend start, so every
    └─ app/seed.py `seed_demo_cases`                 Render deploy re-runs it
       └─ services/research.py `run_country_research(..., {"seed_curated": "true"})`
          └─ `_default_requirements(...)` builds citations_json = json.dumps(source_ids[:1])
             └─ crud.create_requirement_item  → upserts on (country_code, purpose, title)

`source_ids` is EMPTY whenever the StubResearchProvider returns nothing that passes
`_is_official_domain` for that country — which is every SINGAPORE and UNITED STATES run.
So the payload carries `"[]"`, and the update branch assigned it unconditionally.

The fix has a precedent sitting two lines below it in the same function: `review_status` is
already exempted with the reasoning "It is an admin decision about an existing row, not a
property of the seed file". A citation is exactly the same kind of thing.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

import pytest

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import crud, models
from backend.app.services import research


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", future=True)
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    s = Session()
    yield s
    s.close()


def _payload(citations, title="Valid passport (6+ months)"):
    return {
        "id": "seed-generated-uuid",
        "country_code": "SINGAPORE",
        "purpose": "employment",
        "pillar": "IDENTITY",
        "title": title,
        "description": "Hold a passport valid for at least six months.",
        "severity": "BLOCKER",
        "owner": "EMPLOYEE",
        "required_fields_json": json.dumps(["employeeProfile.passportExpiry"]),
        "citations_json": json.dumps(citations),
        "last_verified_at": datetime(2026, 8, 20, 19, 28, 12),
    }


class TestCitationsAreNotBlanked:
    def test_empty_seed_citations_do_not_erase_a_curated_one(self, db):
        """The regression. A startup reseed that found no sources must not un-cite a row."""
        crud.create_requirement_item(db, _payload(["https://www.ica.gov.sg/enter-transit-depart/entering-singapore"]))
        crud.create_requirement_item(db, _payload([]))          # the reseed, no sources found
        row = db.query(models.RequirementItem).one()
        assert json.loads(row.citations_json) == [
            "https://www.ica.gov.sg/enter-transit-depart/entering-singapore"
        ], "a startup reseed blanked a curated citation"

    def test_real_citations_still_update(self, db):
        """The guard must not freeze citations — a seed carrying sources must still win."""
        crud.create_requirement_item(db, _payload(["https://old.example.gov"]))
        crud.create_requirement_item(db, _payload(["https://new.example.gov"]))
        row = db.query(models.RequirementItem).one()
        assert json.loads(row.citations_json) == ["https://new.example.gov"]

    def test_first_insert_with_no_citations_is_allowed(self, db):
        """An uncited row may still be created — the guard is about not LOSING one."""
        crud.create_requirement_item(db, _payload([]))
        row = db.query(models.RequirementItem).one()
        assert json.loads(row.citations_json) == []

    def test_upsert_still_matches_on_country_purpose_title(self, db):
        """Pins the upsert key: the observed row kept its id across reseeds."""
        crud.create_requirement_item(db, _payload(["https://a.gov"]))
        crud.create_requirement_item(db, _payload(["https://b.gov"]))
        assert db.query(models.RequirementItem).count() == 1


class TestReviewStatusIsNotAutoApprovedOrReapproved:
    """The 2026-09-09 regression: a startup reseed re-approved a demoted requirement.

    `services/research._default_requirements` — re-run on every backend start via
    `seed_demo_cases` -> `run_country_research(..., {"seed_curated": "true"})` — was the one
    `create_requirement_item` producer that omitted `review_status`. Because the column
    DEFAULTS to 'approved' (models.RequirementItem.review_status), a fresh insert served
    unreviewed stub content, and a reseed that hit the INSERT branch re-approved a row a
    reviewer had demoted. Migration `20261112000000` §2 demoted the three "Minimum lead time"
    rows (DE/SG/US) to 'pending'; SINGAPORE's drifted back to 'approved' + no citation and
    tripped the requirement-provenance guard. Every other producer already lands 'pending'.
    """

    def _lead_time(self):
        reqs = research._default_requirements("SINGAPORE", "employment", [])
        return next(r for r in reqs if r["title"] == "Minimum lead time")

    def test_default_requirements_all_declare_pending(self):
        """Unit: no auto-research row may rely on the DB's 'approved' default."""
        reqs = research._default_requirements("SINGAPORE", "employment", [])
        assert reqs, "expected default requirements to be produced"
        assert all(r.get("review_status") == "pending" for r in reqs), (
            "an auto-research requirement omitted review_status and would default to 'approved'"
        )

    def test_fresh_insert_is_not_auto_approved(self, db):
        """The regression: a first insert used to fall through to server_default 'approved'."""
        crud.create_requirement_item(db, self._lead_time())
        row = db.query(models.RequirementItem).filter_by(title="Minimum lead time").one()
        assert row.review_status == "pending", (
            "a freshly-seeded auto-research requirement was published without review"
        )

    def test_reseed_does_not_reapprove_a_demoted_row(self, db):
        """The task's exact shape: demote to pending, re-run the seed, stays pending."""
        crud.create_requirement_item(db, self._lead_time())
        row = db.query(models.RequirementItem).filter_by(title="Minimum lead time").one()
        row.review_status = "pending"  # a reviewer / migration 20261112000000 §2 demotes it
        db.commit()
        # the startup reseed runs again: a NEW random id, same natural key, no sources found
        crud.create_requirement_item(db, self._lead_time())
        row = db.query(models.RequirementItem).filter_by(title="Minimum lead time").one()
        assert row.review_status == "pending", "a reseed re-approved a reviewer-demoted row"
        assert db.query(models.RequirementItem).count() == 1

    def test_reseed_preserves_an_approval_and_its_citation(self, db):
        """Symmetric invariant: an admin approval + curated citation survive the reseed."""
        crud.create_requirement_item(db, self._lead_time())
        row = db.query(models.RequirementItem).filter_by(title="Minimum lead time").one()
        row.review_status = "approved"
        row.citations_json = json.dumps(["https://www.ica.gov.sg/reside/LTVP/apply"])
        db.commit()
        crud.create_requirement_item(db, self._lead_time())  # reseed carries [] citations
        row = db.query(models.RequirementItem).filter_by(title="Minimum lead time").one()
        assert row.review_status == "approved", "a reseed un-approved a reviewed row"
        assert json.loads(row.citations_json) == [
            "https://www.ica.gov.sg/reside/LTVP/apply"
        ], "a reseed blanked a curated citation"
