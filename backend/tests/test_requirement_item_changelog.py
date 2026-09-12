"""requirement_items changelog is written on insert and update."""
from __future__ import annotations

import json
import os
from datetime import datetime

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import crud, models
from backend.app.services.requirement_item_changelog import CHANGE_ADDED, CHANGE_REVISED


def _payload(description="Hold a passport.", severity="WARN"):
    return {
        "id": "req-changelog-1",
        "country_code": "NORWAY",
        "purpose": "employment",
        "pillar": "IDENTITY",
        "title": "Valid passport",
        "description": description,
        "severity": severity,
        "owner": "EMPLOYEE",
        "required_fields_json": "[]",
        "citations_json": "[]",
        "last_verified_at": datetime(2026, 9, 12),
    }


def test_insert_and_update_write_changelog():
    engine = create_engine("sqlite://", future=True)
    models.Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, future=True)()
    crud.create_requirement_item(db, _payload())
    rows = db.query(models.RequirementItemChangelog).all()
    assert len(rows) == 1
    assert rows[0].change_type == CHANGE_ADDED

    crud.create_requirement_item(db, _payload(description="Hold a passport valid six months."))
    rows = (
        db.query(models.RequirementItemChangelog)
        .order_by(models.RequirementItemChangelog.changed_at)
        .all()
    )
    assert len(rows) == 2
    assert rows[1].change_type == CHANGE_REVISED
    prev = json.loads(rows[1].previous_value)
    assert prev["description"] == "Hold a passport."
    db.close()


def test_catalog_write_survives_missing_changelog_table():
    engine = create_engine("sqlite://", future=True)
    models.RequirementItem.__table__.create(engine)
    db = sessionmaker(bind=engine, future=True)()
    item = crud.create_requirement_item(db, _payload())
    assert item.id == "req-changelog-1"
    db.close()
