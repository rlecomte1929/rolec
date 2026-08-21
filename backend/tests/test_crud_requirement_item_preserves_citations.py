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
