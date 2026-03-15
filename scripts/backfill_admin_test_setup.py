#!/usr/bin/env python3
"""
One-time non-destructive backfill to make Test company the operational validation company.

Actions:
1. Link all profiles/users to Test company unless already linked elsewhere.
2. Link all assignments/cases to Test company if missing company linkage.
3. Link the existing policy (latest by created_at) to Test company.
4. Ensure Test company has at least one HR user if one can be inferred.

- Does not duplicate data.
- Only updates missing links; does not overwrite valid existing links.
- Produces a clear admin reconciliation/backfill report in logs.
- If ambiguous, marks record as ambiguous and skips (no destructive guess).

Run from repo root:
  python scripts/backfill_admin_test_setup.py

Return (printed and in exit code): records found, records linked, ambiguous skipped, summary.
"""
from __future__ import print_function

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

from backend.database import Database


def main() -> int:
    db = Database()
    report = {
        "records_found": {},
        "records_linked": {},
        "ambiguous_skipped": [],
    }

    # Resolve Test company
    with db.engine.connect() as conn:
        from sqlalchemy import text
        row = conn.execute(
            text("SELECT id, name FROM companies WHERE LOWER(TRIM(name)) = LOWER(TRIM(:name)) LIMIT 1"),
            {"name": "Test company"},
        ).fetchone()
    if not row:
        log.error("Company 'Test company' not found. Create it first.")
        _print_report(report, ok=False)
        return 1
    test_company_id = row._mapping["id"]
    test_company_name = row._mapping["name"]

    # --- 1. Snapshot: records found (reconciliation report) ---
    recon = db.get_reconciliation_report()
    summary = recon.get("summary") or {}
    report["records_found"] = {
        "profiles_without_company": summary.get("people_without_company_count", 0),
        "assignments_cases_without_company": summary.get("assignments_without_company_count", 0),
        "policies_total": summary.get("policies_count", 0),
        "policies_without_company": summary.get("policies_without_company_count", 0),
    }
    log.info(
        "Records found: %d profiles unlinked, %d assignments/cases without company, %d policies (%d without company)",
        report["records_found"]["profiles_without_company"],
        report["records_found"]["assignments_cases_without_company"],
        report["records_found"]["policies_total"],
        report["records_found"]["policies_without_company"],
    )

    # --- 2. Link profiles to Test company (only those with no company) ---
    result_profiles = db.backfill_profiles_to_test_company("Test company")
    if not result_profiles.get("ok"):
        report["ambiguous_skipped"].append(
            "profiles: " + result_profiles.get("error", "backfill failed")
        )
        log.warning("Profile backfill skipped or failed: %s", result_profiles.get("error"))
    else:
        report["records_linked"]["profiles"] = result_profiles.get("profiles_updated", 0)
        log.info("Linked %d profile(s) to Test company", report["records_linked"]["profiles"])

    # --- 3. Link assignments/cases to Test company (only those with no company) ---
    result_cases = db.backfill_assignments_to_test_company("Test company")
    if not result_cases.get("ok"):
        report["ambiguous_skipped"].append(
            "assignments/cases: " + result_cases.get("error", "backfill failed")
        )
        log.warning("Assignments backfill skipped or failed: %s", result_cases.get("error"))
    else:
        report["records_linked"]["relocation_cases"] = result_cases.get("cases_updated", 0)
        log.info("Linked %d relocation case(s) (assignments visible by company) to Test company", report["records_linked"]["relocation_cases"])

    # --- 4. Link latest policy to Test company ---
    result_policy = db.backfill_link_latest_policy_to_test_company("Test company")
    if not result_policy.get("ok"):
        report["ambiguous_skipped"].append(
            "policy: " + result_policy.get("error", "backfill failed")
        )
        log.warning("Policy backfill skipped or failed: %s", result_policy.get("error"))
    else:
        report["records_linked"]["policy"] = 1 if result_policy.get("linked") else 0
        if result_policy.get("linked"):
            log.info("Linked policy %s to Test company", result_policy.get("policy_id"))
        else:
            log.info("No policy to link (no company_policies rows)")

    # --- 5. Ensure Test company has at least one HR user if inferable ---
    result_hr = db.ensure_test_company_has_hr_user("Test company")
    if result_hr.get("ok"):
        if result_hr.get("hr_added"):
            report["records_linked"]["hr_user_added"] = 1
            log.info("Added 1 HR user for Test company (inferred from ADMIN profile)")
        else:
            log.info("Test company already has at least one HR user")
    else:
        reason = result_hr.get("ambiguous_reason") or "unknown"
        report["ambiguous_skipped"].append("hr_user: " + reason)
        log.warning("HR user not added (ambiguous): %s", reason)

    # --- Print admin reconciliation / backfill report ---
    _print_report(report, test_company_id=test_company_id, test_company_name=test_company_name)
    return 0


def _print_report(
    report: dict,
    ok: bool = True,
    test_company_id: str = "",
    test_company_name: str = "Test company",
) -> None:
    print()
    print("========== Admin Test Setup Backfill Report ==========")
    print("Target company: %s (id=%s)" % (test_company_name, test_company_id or "—"))
    print()
    print("1. RECORDS FOUND (before link)")
    for k, v in (report.get("records_found") or {}).items():
        print("   - %s: %s" % (k, v))
    print()
    print("2. RECORDS LINKED TO TEST COMPANY")
    linked = report.get("records_linked") or {}
    if not linked:
        print("   (none)")
    for k, v in linked.items():
        print("   - %s: %s" % (k, v))
    print()
    print("3. AMBIGUOUS RECORDS SKIPPED")
    ambiguous = report.get("ambiguous_skipped") or []
    if not ambiguous:
        print("   (none)")
    for a in ambiguous:
        print("   - %s" % a)
    print()
    if ok:
        print("Backfill complete.")
        print()
        print("Verification checklist (Admin console):")
        print("  [ ] People: Filter by '%s' — at least one profile visible" % test_company_name)
        print("  [ ] Assignments: Filter by '%s' — assignments/cases visible" % test_company_name)
        print("  [ ] Policies: Select '%s' — at least one policy visible" % test_company_name)
        print("  [ ] HR user: At least one HR user for '%s' (or add manually)" % test_company_name)
    print("=======================================================")
    print()


if __name__ == "__main__":
    sys.exit(main())
