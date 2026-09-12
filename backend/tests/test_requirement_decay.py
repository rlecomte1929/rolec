"""RP-MEM-002: approved requirement_items decay by last_verified_at, and stay served.

A 100-day-old immigration-pillar row with a 90-day cycle is stale. A same-day
stamp is not. Decay is a label — `review_status=approved` still reaches the
catalog. Silently un-approving would empty Case Command.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import crud, models
from backend.app.services import requirement_decay as decay


NOW = datetime(2026, 9, 12, 12, 0, 0)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", future=True)
    models.Base.metadata.create_all(engine, tables=[models.RequirementItem.__table__])
    with sessionmaker(bind=engine)() as session:
        yield session


def _payload(title: str, **over):
    base = dict(
        id=f"id-{title.replace(' ', '-')}",
        country_code="NORWAY",
        purpose="employment",
        pillar="IMMIGRATION",
        title=title,
        description="…",
        severity="WARN",
        owner="EMPLOYEE",
        required_fields_json="[]",
        citations_json="[]",
        verification_status="corpus_grounded",
        review_status="approved",
        last_verified_at=NOW,
    )
    base.update(over)
    return base


def test_hundred_day_old_immigration_item_is_stale():
    row = SimpleNamespace(
        pillar="IMMIGRATION",
        last_verified_at=NOW - timedelta(days=100),
        review_status="approved",
    )
    assert decay.cycle_days_for("IMMIGRATION") == 90
    assert decay.is_stale(NOW, row) is True


def test_same_day_item_is_not_stale():
    row = SimpleNamespace(
        pillar="IMMIGRATION",
        last_verified_at=NOW,
        review_status="approved",
    )
    assert decay.is_stale(NOW, row) is False


def test_residence_uses_the_ninety_day_cycle():
    row = SimpleNamespace(
        pillar="RESIDENCE",
        last_verified_at=NOW - timedelta(days=91),
        review_status="approved",
    )
    assert decay.cycle_days_for("RESIDENCE") == 90
    assert decay.is_stale(NOW, row) is True


def test_housing_cycle_is_one_year():
    fresh = SimpleNamespace(
        pillar="HOUSING",
        last_verified_at=NOW - timedelta(days=100),
        review_status="approved",
    )
    stale = SimpleNamespace(
        pillar="HOUSING",
        last_verified_at=NOW - timedelta(days=366),
        review_status="approved",
    )
    assert decay.cycle_days_for("HOUSING") == 365
    assert decay.is_stale(NOW, fresh) is False
    assert decay.is_stale(NOW, stale) is True


def test_stale_approved_item_is_still_served(db):
    crud.create_requirement_item(
        db,
        _payload(
            "Skattekort",
            last_verified_at=NOW - timedelta(days=100),
            pillar="IMMIGRATION",
        ),
    )
    served = crud.list_requirements(db, "NORWAY")
    assert [r.title for r in served] == ["Skattekort"]
    assert served[0].review_status == "approved"
    assert decay.is_stale(NOW, served[0]) is True


def test_cli_prints_country_and_id_for_fixtures(tmp_path, capsys):
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts" / "report_requirement_decay.py"
    spec = importlib.util.spec_from_file_location("report_requirement_decay", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    main = mod.main

    fixture = tmp_path / "decay_fixture.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "country_code": "NORWAY",
                    "id": "ri-stale-1",
                    "title": "Skattekort",
                    "pillar": "IMMIGRATION",
                    "review_status": "approved",
                    "last_verified_at": (NOW - timedelta(days=100)).isoformat(),
                },
                {
                    "country_code": "NORWAY",
                    "id": "ri-fresh-1",
                    "title": "Fresh stamp",
                    "pillar": "IMMIGRATION",
                    "review_status": "approved",
                    "last_verified_at": NOW.isoformat(),
                },
            ]
        ),
        encoding="utf-8",
    )
    rc = main(["--fixture", str(fixture), "--now", NOW.isoformat()])
    out = capsys.readouterr().out
    assert rc == 0
    assert "NORWAY" in out
    assert "ri-stale-1" in out
    assert "ri-fresh-1" not in out
