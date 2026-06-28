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
    re-seeder ('Test company'), the unambiguous '… (Seed)' marker, and the
    'Brand New Co <epoch>' tenants the Wave-3 onboarding e2e flow creates
    (AIQ-1325a). We do NOT pattern on 'Test%' / 'TestCo%' etc.: that would hide
    real/demo tenants such as 'Testing April'. The 'Brand New Co ' literal keeps
    its trailing space so a hypothetical real 'Brand New Co' (no suffix) is not
    over-matched. Remaining synthetic pollution (e.g. 'TestCo WZ4 …') still needs
    a proper is_test marker or routing e2e off prod, not fragile name matching.
    """
    names = ", ".join("'" + n.replace("'", "''") + "'" for n in _TEST_COMPANY_NAMES)
    return (
        f"({name_col} IS NULL OR ("
        f"{name_col} NOT IN ({names}) "
        f"AND {name_col} NOT LIKE 'Probe ISO-%' "
        f"AND {name_col} NOT LIKE 'Brand New Co %' "
        f"AND {name_col} NOT LIKE '%(Seed)%'))"
    )


def exclude_test_people(email_col: str = "email") -> str:
    """SQL fragment that is TRUE for real (non-seed) person rows."""
    return f"COALESCE({email_col}, '') NOT LIKE '{_TEST_EMAIL_LIKE}'"


# ── Write-time classifiers (PRODSEED-3 / AIQ-1130) ──────────────────────────────
# The durable fix flips the same patterns from a read-time SQL filter to a one-time
# `is_test` stamp set when a synthetic row is *created*. These predicates power that
# auto-stamp (companies/profiles creation) and mirror the SQL fragments above so a
# tenant is classified identically whether it's flagged at write time or backfilled
# by the migration. Demo tenants are intentionally NOT matched (see module docstring).

# Company-name prefixes the verify/e2e seeders use ('Probe ISO-…' from the tenant-
# isolation probe, 'Probe RLS-…' from verify_tenant_isolation.py, 'Brand New Co …'
# from the Wave-3 onboarding e2e flow — AIQ-1325a). New 'Brand New Co <epoch>'
# tenants are thus stamped is_test=true at create time, while the read-time
# exclude_test_companies() LIKE covers rows already in prod.
_TEST_COMPANY_PREFIXES = ("Probe ISO-", "Probe RLS-", "Brand New Co ")

# Synthetic email domains: '@testco.com' (e2e runner + verify_fresh_onboarding) and
# '@probe.test' (verify_tenant_isolation.py). Kept as exact suffixes so real domains
# like '@testcompany.com' / '@testingapril.com' (the demo tenants) never match.
_TEST_EMAIL_DOMAINS = ("@testco.com", "@probe.test")


def looks_like_test_company(name: "str | None") -> bool:
    """True if a company name matches a known synthetic-seeder pattern."""
    n = (name or "").strip()
    if not n:
        return False
    if n in _TEST_COMPANY_NAMES:
        return True
    if any(n.startswith(p) for p in _TEST_COMPANY_PREFIXES):
        return True
    if "(Seed)" in n:
        return True
    return False


def looks_like_test_email(email: "str | None") -> bool:
    """True if an email is on a synthetic seeder domain (@testco.com / @probe.test)."""
    e = (email or "").strip().lower()
    return any(e.endswith(d) for d in _TEST_EMAIL_DOMAINS)


# ── Read-time display scrub (AIQ-1325b) ─────────────────────────────────────────
# Verify/e2e runs against prod send messages whose text is prefixed '[verify] '.
# Those leak into inbox thread previews/titles. Strip the marker for DISPLAY only
# (the stored row is untouched) so a real customer / demo guest never sees it. The
# prefix is produced by an external runner (no committed code emits it), so this is
# a defensive read-time guard, not a one-time purge.
_VERIFY_MARKER = "[verify]"


def strip_verify_prefix(text: "str | None") -> "str | None":
    """Remove a single leading '[verify]' marker (+ any following whitespace) from
    inbox-facing message text. Case-insensitive; a no-op for normal text, None, or
    empty. Non-destructive (display-time only)."""
    if not text:
        return text
    if text[: len(_VERIFY_MARKER)].lower() == _VERIFY_MARKER:
        return text[len(_VERIFY_MARKER):].lstrip()
    return text
