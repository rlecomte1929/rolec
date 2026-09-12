"""RP-MEM-002 — visible decay for served `requirement_items`.

`last_verified_at` already exists. Cycle length is a code-side map keyed by
pillar so Demo Day does not need a migration. Stale approved rows stay served;
callers label them. Never un-approve from here.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any, Iterable, List, Optional, Sequence

from sqlalchemy.orm import Session

CYCLE_DAYS_BY_PILLAR = {
    "IMMIGRATION": 90,
    "RESIDENCE": 90,
    "IDENTITY": 90,
    "EMPLOYMENT": 90,
    "HOUSING": 365,
    "HEALTHCARE": 365,
    "TAX": 90,
    "BANKING": 365,
}
DEFAULT_CYCLE_DAYS = 365


def cycle_days_for(pillar: Optional[str]) -> int:
    key = (pillar or "").strip().upper()
    return CYCLE_DAYS_BY_PILLAR.get(key, DEFAULT_CYCLE_DAYS)


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_stale(item: Any, now: Optional[datetime] = None) -> bool:
    """True when an approved (or any) item's last_verified_at is past its pillar cycle."""
    stamp = getattr(item, "last_verified_at", None)
    if stamp is None:
        return False
    if isinstance(stamp, str):
        try:
            stamp = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            return False
    if not isinstance(stamp, datetime):
        return False
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    age = _as_aware(clock) - _as_aware(stamp)
    return age.days > cycle_days_for(getattr(item, "pillar", None))


def stale_approved(rows: Iterable[Any], now: Optional[datetime] = None) -> List[Any]:
    out = []
    for row in rows:
        status = (getattr(row, "review_status", None) or "").strip().lower()
        if status != "approved":
            continue
        if is_stale(row, now=now):
            out.append(row)
    return out


def list_stale_approved(db: Session, now: Optional[datetime] = None) -> List[Any]:
    from .. import models

    rows = (
        db.query(models.RequirementItem)
        .filter(models.RequirementItem.review_status == "approved")
        .all()
    )
    return stale_approved(rows, now=now)


def report_rows(rows: Sequence[Any], now: Optional[datetime] = None) -> List[dict]:
    clock = now or datetime.now(timezone.utc)
    report = []
    for row in rows:
        stamp = getattr(row, "last_verified_at", None)
        age_days = None
        if isinstance(stamp, datetime):
            age_days = (_as_aware(clock) - _as_aware(stamp)).days
        report.append(
            {
                "country_code": getattr(row, "country_code", None),
                "id": getattr(row, "id", None),
                "title": getattr(row, "title", None),
                "pillar": getattr(row, "pillar", None),
                "age_days": age_days,
                "cycle_days": cycle_days_for(getattr(row, "pillar", None)),
            }
        )
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="List approved requirement_items past review cycle.")
    parser.parse_args(argv)
    from ..db import SessionLocal

    with SessionLocal() as db:
        stale = list_stale_approved(db)
        payload = report_rows(stale)
        json.dump({"count": len(payload), "by_country": payload}, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
