#!/usr/bin/env python3
"""List approved requirement_items whose last_verified_at is past the pillar cycle.

Read-only. Never writes review_status. Stale rows stay served.

Usage (from repo root):
  python scripts/report_requirement_decay.py --fixture /tmp/rows.json --now 2026-09-12T12:00:00
  python scripts/report_requirement_decay.py   # live DB when DATABASE_URL is set
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, List

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.requirement_decay import format_decay_report  # noqa: E402


def _parse_now(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _rows_from_fixture(path: str) -> List[Any]:
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    return [SimpleNamespace(**item) for item in payload]


def _rows_from_db() -> List[Any]:
    from backend.app.db import SessionLocal
    from backend.app.models import RequirementItem

    with SessionLocal() as session:
        return (
            session.query(RequirementItem)
            .filter(RequirementItem.review_status == "approved")
            .all()
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        help="JSON list of {country_code,id,title,pillar,review_status,last_verified_at}",
    )
    parser.add_argument("--now", help="ISO timestamp for age math (tests)")
    args = parser.parse_args(argv)

    now = _parse_now(args.now)
    if args.fixture:
        rows = _rows_from_fixture(args.fixture)
    elif os.environ.get("DATABASE_URL"):
        rows = _rows_from_db()
    else:
        rows = []

    sys.stdout.write(format_decay_report(rows, now))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
