#!/usr/bin/env python3
"""
Backfill all existing profiles to Test company.
- Finds company named "Test company" (or creates it if --create-company)
- Assigns every profile with no company_id to that company
- Defaults role to EMPLOYEE unless in admin_allowlist (ADMIN) or hr_users (HR)
- Updates hr_users and employees company_id to match
- Does not create duplicate profiles

Run from repo root:
  python scripts/backfill_people_to_test_company.py
  python scripts/backfill_people_to_test_company.py --create-company   # create Test company if missing
"""
import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import Database


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill profiles to Test company")
    parser.add_argument("--create-company", action="store_true", help="Create 'Test company' if not found")
    args = parser.parse_args()

    db = Database()
    result = db.backfill_profiles_to_test_company("Test company")
    if not result.get("ok") and result.get("error", "").endswith("not found") and args.create_company:
        company_id = str(uuid.uuid4())
        db.create_company(
            company_id=company_id,
            name="Test company",
            country=None,
            size_band=None,
            status="active",
            plan_tier="low",
        )
        print("Created 'Test company' (id=%s). Running backfill..." % company_id)
        result = db.backfill_profiles_to_test_company("Test company")
    if not result.get("ok"):
        print(result.get("error", "Backfill failed"))
        return 1
    print(
        "Backfill complete: %s profiles linked to '%s' (id=%s)"
        % (result["profiles_updated"], result["company_name"], result["company_id"])
    )
    print("Roles defaulted (where missing): %s" % result.get("role_defaulted", 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
