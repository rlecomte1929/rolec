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
    # AIQ-2327: the seeder families that postdate AIQ-913 — 'Google IE <digits>',
    # 'Google Ireland T18-<A>-<digits>', 'CPY <name>', 'VCo/WCo <digits>', 'Company 1',
    # and a broad '%test%' (Test, TestCompany, YvesTestCompany …). LOWER()+LIKE so it
    # matches case-insensitively on BOTH Postgres and SQLite (no ILIKE / regex). The
    # demo tenant 'Testing April' is excluded from the '%test%' rule explicitly.
    return (
        f"({name_col} IS NULL OR ("
        f"{name_col} NOT IN ({names}) "
        f"AND {name_col} NOT LIKE 'Probe ISO-%' "
        f"AND {name_col} NOT LIKE 'Probe RLS-%' "
        f"AND {name_col} NOT LIKE 'Brand New Co %' "
        f"AND {name_col} NOT LIKE 'Test Drive %' "
        f"AND {name_col} NOT LIKE '%(Seed)%' "
        f"AND {name_col} NOT LIKE 'Google IE %' "
        f"AND {name_col} NOT LIKE 'Google Ireland T18-%' "
        f"AND {name_col} NOT LIKE 'CPY %' "
        f"AND {name_col} NOT LIKE 'VCo %' "
        f"AND {name_col} NOT LIKE 'WCo %' "
        f"AND {name_col} <> 'Company 1' "
        f"AND NOT (LOWER({name_col}) LIKE '%test%' AND LOWER({name_col}) <> 'testing april')))"
    )


def exclude_test_people(email_col: str = "email") -> str:
    """SQL fragment that is TRUE for real (non-seed) person rows.

    AIQ-2327: extends the original ``@testco.com`` domain with the seeder families
    that pollute leads/people — the resend.app relay, ``@example.com`` fixtures,
    ``qa-proj-*`` and the 1218 signups on Romain's hotmail with ``+t18/+emp_run/…``
    plus-aliases. LOWER()+LIKE so it is safe on both Postgres and SQLite (no ILIKE /
    regex). A real address with no ``+`` alias (romain_lecomte@hotmail.com) never
    matches, and ``@testcompany.com`` is distinct from ``@testco.com``.
    """
    e = f"COALESCE({email_col}, '')"
    le = f"LOWER({e})"
    return (
        f"({e} NOT LIKE '%@testco.com' "
        f"AND {e} NOT LIKE '%@reloulexei.resend.app' "
        f"AND {e} NOT LIKE '%@example.com' "
        f"AND {le} NOT LIKE 'qa-proj-%' "
        f"AND {le} NOT LIKE '%+t18%@hotmail.com' "
        f"AND {le} NOT LIKE '%+emp_run%@hotmail.com' "
        f"AND {le} NOT LIKE '%+hr_run%@hotmail.com' "
        f"AND {le} NOT LIKE '%+twin%@hotmail.com' "
        f"AND {le} NOT LIKE '%+dryrun%@hotmail.com' "
        f"AND {le} NOT LIKE '%+qa%@hotmail.com')"
    )


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
# AIQ-2327 adds the newer seeder families: 'Google IE <digits>', 'Google Ireland
# T18-<A>-<digits>', 'CPY <name>', 'VCo/WCo <digits>'. 'Company 1' (exact) and the
# broad '%test%' rule are handled in looks_like_test_company directly.
_TEST_COMPANY_PREFIXES = (
    "Probe ISO-", "Probe RLS-", "Brand New Co ", "Test Drive ",
    "Google IE ", "Google Ireland T18-", "CPY ", "VCo ", "WCo ",
)

# Synthetic email domains: '@testco.com' (e2e runner) / '@probe.test'
# (verify_tenant_isolation.py) / '@reloulexei.resend.app' (the outbound relay) /
# '@example.com' (fixtures). Exact suffixes so real domains like '@testcompany.com' /
# '@testingapril.com' (demo tenants) never match. Hotmail plus-aliases and 'qa-proj-'
# prefixes are handled in looks_like_test_email directly.
_TEST_EMAIL_DOMAINS = ("@testco.com", "@probe.test", "@reloulexei.resend.app", "@example.com")

# Hotmail plus-alias segments the signup seeders use (roma+t18empb_…@hotmail.com).
_TEST_HOTMAIL_ALIASES = ("+t18", "+emp_run", "+hr_run", "+twin", "+dryrun", "+qa")


def looks_like_test_company(name: "str | None") -> bool:
    """True if a company name matches a known synthetic-seeder pattern."""
    n = (name or "").strip()
    if not n:
        return False
    if n in _TEST_COMPANY_NAMES or n == "Company 1":
        return True
    if any(n.startswith(p) for p in _TEST_COMPANY_PREFIXES):
        return True
    if "(Seed)" in n:
        return True
    low = n.lower()
    if "test" in low and low != "testing april":
        return True
    return False


def looks_like_test_email(email: "str | None") -> bool:
    """True if an email is a synthetic seeder address (domain, qa-proj prefix, or a
    hotmail plus-alias). Never matches a real address with no '+' alias."""
    e = (email or "").strip().lower()
    if not e:
        return False
    if any(e.endswith(d) for d in _TEST_EMAIL_DOMAINS):
        return True
    if e.startswith("qa-proj-"):
        return True
    if e.endswith("@hotmail.com") and any(a in e for a in _TEST_HOTMAIL_ALIASES):
        return True
    return False


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
