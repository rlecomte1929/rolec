"""RP-MEM-002 — decay uses existing last_verified_at; stale approved rows stay served."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.app.services.requirement_decay import (
    cycle_days_for,
    is_stale,
    report_rows,
    stale_approved,
)


def test_immigration_pillar_is_stale_after_100_days():
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    old = SimpleNamespace(
        pillar="IMMIGRATION",
        last_verified_at=now - timedelta(days=100),
        review_status="approved",
    )
    fresh = SimpleNamespace(
        pillar="IMMIGRATION",
        last_verified_at=now,
        review_status="approved",
    )
    assert cycle_days_for("IMMIGRATION") == 90
    assert is_stale(old, now=now)
    assert not is_stale(fresh, now=now)


def test_housing_uses_365_day_cycle():
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    item = SimpleNamespace(
        pillar="HOUSING",
        last_verified_at=now - timedelta(days=100),
        review_status="approved",
    )
    assert not is_stale(item, now=now)


def test_stale_approved_does_not_include_pending():
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    rows = [
        SimpleNamespace(
            id="1",
            country_code="NORWAY",
            title="Tax card",
            pillar="RESIDENCE",
            review_status="approved",
            last_verified_at=now - timedelta(days=100),
        ),
        SimpleNamespace(
            id="2",
            country_code="NORWAY",
            title="Pending",
            pillar="RESIDENCE",
            review_status="pending",
            last_verified_at=now - timedelta(days=100),
        ),
    ]
    flagged = stale_approved(rows, now=now)
    assert [r.id for r in flagged] == ["1"]
    report = report_rows(flagged, now=now)
    assert report[0]["country_code"] == "NORWAY"
    assert report[0]["id"] == "1"
    assert report[0]["cycle_days"] == 90
