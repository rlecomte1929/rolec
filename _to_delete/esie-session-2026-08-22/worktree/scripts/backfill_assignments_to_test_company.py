#!/usr/bin/env python3
"""
Backfill all relocation cases (assignments) to Test company.
- Finds company named "Test company"
- Sets company_id on every relocation_case that has no company_id
- Assignments then appear when filtering by Test company in Admin Assignments
- Does not duplicate records; only updates existing rows

Run from repo root:
  python scripts/backfill_assignments_to_test_company.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import Database


def main() -> int:
    db = Database()
    result = db.backfill_assignments_to_test_company("Test company")
    if not result.get("ok"):
        print(result.get("error", "Backfill failed"))
        return 1
    print(
        "Backfill complete: %s relocation case(s) linked to '%s' (id=%s)"
        % (result["cases_updated"], result["company_name"], result["company_id"])
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
