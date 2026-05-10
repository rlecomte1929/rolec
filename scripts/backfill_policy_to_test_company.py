#!/usr/bin/env python3
"""
Link the most recently created company_policy to Test company.
- Finds company named "Test company"
- Finds the latest company_policy (by created_at)
- Sets that policy's company_id to Test company so it appears in Admin Policies for Test company

Run from repo root:
  python scripts/backfill_policy_to_test_company.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import Database


def main() -> int:
    db = Database()
    result = db.backfill_link_latest_policy_to_test_company("Test company")
    if not result.get("ok"):
        print(result.get("error", "Backfill failed"))
        return 1
    if result.get("linked"):
        print(
            "Backfill complete: policy %s linked to '%s' (id=%s)"
            % (result["policy_id"], result["company_name"], result["company_id"])
        )
    else:
        print(
            "No policy to link. Company '%s' (id=%s) is ready; create a policy in the HR policy workspace to backfill later."
            % (result["company_name"], result["company_id"])
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
