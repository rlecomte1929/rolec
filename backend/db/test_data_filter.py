"""Synthetic test/seed-record exclusion for admin read surfaces (AIQ-913).

Production is continuously re-seeded with throwaway tenants by e2e / verify
flows that run against prod (emails ``…@testco.com`` — ``emp_run_``/``hr_run_``/
``emp_uxfix_``/``F17…``; company names ``Other Corp``, ``Probe ISO-*``,
``Test Co (Seed)``, ``Test company``). A one-time purge can't hold — the rows
reappear within minutes — so the admin **Companies list** and **Mobility-center
people index** filter these out at *read time* instead.

Non-destructive: the rows remain in the tables (the test flows depend on them);
they're simply not shown on the admin surfaces a human / demo guest looks at.

Each helper returns a SQL boolean fragment that is **TRUE for non-test (real)
rows**, to be AND-ed into a WHERE clause. Patterns are fixed literals (no user
input — safe to inline) and evaluate identically on PostgreSQL and SQLite.
"""
from __future__ import annotations

# Exact company names the e2e/verify seeders create. Extend here if new
# synthetic names appear (keep the list tight so real tenants are never hidden).
_TEST_COMPANY_NAMES = ("Other Corp", "Test Co (Seed)", "Test company")

# The consistent synthetic email domain. Covers every seeder signature
# (emp_run_/hr_run_/emp_uxfix_/hr_uxfix_/emp_f17_ … @testco.com).
_TEST_EMAIL_LIKE = "%@testco.com"


def exclude_test_companies(name_col: str = "name") -> str:
    """SQL fragment that is TRUE for real (non-seed) company rows.

    Deliberately narrow — only the task's named patterns plus the active
    re-seeder ('Test company') and the unambiguous '… (Seed)' marker. We do NOT
    pattern on 'Test%' / 'TestCo%' etc.: that would hide real/demo tenants such
    as 'Testing April'. Broader synthetic-tenant pollution (e.g. 'Brand New Co
    <ts>', 'TestCo WZ4 …') needs a proper is_test marker or routing e2e off prod
    (AIQ-913 root-cause follow-up), not fragile name matching.
    """
    names = ", ".join("'" + n.replace("'", "''") + "'" for n in _TEST_COMPANY_NAMES)
    return (
        f"({name_col} IS NULL OR ("
        f"{name_col} NOT IN ({names}) "
        f"AND {name_col} NOT LIKE 'Probe ISO-%' "
        f"AND {name_col} NOT LIKE '%(Seed)%'))"
    )


def exclude_test_people(email_col: str = "email") -> str:
    """SQL fragment that is TRUE for real (non-seed) person rows."""
    return f"COALESCE({email_col}, '') NOT LIKE '{_TEST_EMAIL_LIKE}'"
