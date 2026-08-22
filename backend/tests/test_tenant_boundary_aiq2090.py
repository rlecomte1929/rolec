"""[AIQ-2090] The three tenant-boundary holes on the HR path, pinned.

Each test here FAILS against origin/main. Verified by restoring main's sources and
re-running — see the PR.

WHAT WAS WRONG
--------------
1. PUBLIC signup joined an existing tenant by typed name.
   `POST /api/auth/register` -> `find_or_create_company_by_name`, a
   `LOWER(TRIM(name))` match. Type a customer's company name and the new account was
   linked into their workspace: every HR API call is scoped by the profile's
   company_id, so the stranger got their cases, employees and policies.

2. The legacy `/api/hr/policies` CRUD had NO ownership check.
   `GET/PUT/DELETE /api/hr/policies/{policy_id}` operated on a bare id — cross-tenant
   read, OVERWRITE and DELETE. `GET /api/hr/policies` took `companyEntity` as a
   client-supplied query parameter defaulting to None, returning every tenant's rows.
   Deleted rather than hardened: 0 rows in production, the only frontend consumer was
   unmounted, and `/api/hr/policy-config/*` is the live stack.

3. `get_published_hr_policy_for_employee` had no company filter.
   `SELECT id, policy_json FROM hr_policies WHERE status = 'published'` — every
   tenant's — and its live caller (`GET /api/employee/policy/applicable`) passed no
   company. The first published policy from ANY company matching the band and
   assignment type was returned to the employee as theirs, benefit caps included.

None of these had fired: `hr_policies` holds 0 rows because its only writer,
`_seed_default_hr_policy`, is gated behind `_db_scheme == "sqlite"`. Latent, not live.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import re

import pytest

from backend.main import app


_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# ── Hole 2: the unguarded endpoints are gone ────────────────────────────────

@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/hr/policies"),
        ("POST", "/api/hr/policies"),
        ("POST", "/api/hr/policies/upload"),
        ("GET", "/api/hr/policies/{policy_id}"),
        ("PUT", "/api/hr/policies/{policy_id}"),
        ("DELETE", "/api/hr/policies/{policy_id}"),
    ],
)
def test_legacy_unguarded_policy_routes_are_not_mounted(method, path):
    """You cannot leak through an endpoint that does not exist."""
    for route in app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            pytest.fail(
                f"{method} {path} is still mounted — it had no ownership check, so a "
                "valid id from another tenant was readable, writable and deletable."
            )


def test_the_case_scoped_policy_endpoint_survived():
    """`GET /api/hr/policy?caseId=` is a DIFFERENT endpoint and is correctly guarded.

    The name collision matters: the existing guard test
    `HrComplianceReadTenantScopeGuardTests.test_get_hr_policy_scoped` asserts on a
    function named `get_hr_policy` — which is THIS one — and never covered
    `get_hr_policy_by_id`. Deleting the wrong one would have removed a live surface.
    """
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/hr/policy" in paths


def test_policy_config_stack_is_untouched():
    """The live subsystem must still be there — this change removes only the legacy one."""
    paths = {getattr(r, "path", None) for r in app.routes}
    assert any(p and p.startswith("/api/hr/policy-config") for p in paths)


# ── Hole 1: signup cannot join a tenant by typed name ───────────────────────

def test_signup_does_not_call_the_name_matching_join():
    """Guard at source: the public register handler must not reach the name matcher."""
    with open(os.path.join(_REPO, "backend", "app", "routers", "auth.py"), encoding="utf-8") as fh:
        src = fh.read()
    # Only the explanatory comment may mention it; no call may remain.
    calls = re.findall(r"db\.find_or_create_company_by_name\s*\(", src)
    assert calls == [], (
        "auth.py still calls find_or_create_company_by_name — a LOWER(TRIM(name)) "
        "match on a PUBLIC form is not an authorisation check."
    )
    assert "db.create_company_for_self_serve_signup(" in src


def test_self_serve_signup_helper_always_creates(monkeypatch):
    """It must never return an existing company's id, whatever the name collision."""
    from backend.db import companies as companies_mod

    created = []

    class _Fake(companies_mod.CompaniesMixin):  # type: ignore[name-defined]
        def create_company(self, company_id, name, status=None, plan_tier=None, size_band=None, **kw):
            created.append((company_id, name))

    fake = _Fake()
    first = fake.create_company_for_self_serve_signup("Acme")
    second = fake.create_company_for_self_serve_signup("acme")   # same name, different case
    assert first and second and first != second, "a name collision must not reuse an id"
    assert len(created) == 2
    # The typed name is preserved verbatim — no invented "Acme (2)".
    assert created[0][1] == "Acme" and created[1][1] == "acme"


def test_blank_company_name_creates_nothing():
    from backend.db import companies as companies_mod

    class _Fake(companies_mod.CompaniesMixin):  # type: ignore[name-defined]
        def create_company(self, *a, **kw):
            raise AssertionError("must not create a company for a blank name")

    assert _Fake().create_company_for_self_serve_signup("   ") is None


# ── Hole 3: the employee policy read is company-scoped and fail-closed ──────

class _StubConn:
    def __init__(self, rows, captured):
        self._rows = rows
        self._captured = captured

    def execute(self, stmt, params=None):
        self._captured.append((str(stmt), params or {}))
        return self

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _StubEngine:
    def __init__(self, rows, captured):
        self._rows, self._captured = rows, captured

    def connect(self):
        return _StubConn(self._rows, self._captured)


def _policies_mixin(rows, captured):
    from backend.db import policies as policies_mod

    class _Fake(policies_mod.PoliciesMixin):  # type: ignore[name-defined]
        engine = _StubEngine(rows, captured)

    return _Fake()


def test_employee_policy_read_without_a_company_returns_nothing():
    """FAIL-CLOSED. Previously this returned the first published policy in the table —
    another company's — because the live caller passed no company at all."""
    captured: list = []
    obj = _policies_mixin([], captured)
    assert obj.get_published_hr_policy_for_employee(
        employee_band="Band A", assignment_type="Long-Term"
    ) is None
    assert captured == [], "no company scope must mean no query at all"


def test_employee_policy_read_filters_by_company_in_sql():
    captured: list = []
    obj = _policies_mixin([], captured)
    obj.get_published_hr_policy_for_employee(
        employee_band="Band A", assignment_type="Long-Term", company_entity="co-1"
    )
    assert captured, "expected a query"
    sql, params = captured[0]
    assert "company_entity = :company" in sql, (
        "the company predicate must be IN THE SQL — filtering in Python after selecting "
        "every tenant's rows is what this fixes"
    )
    assert params.get("company") == "co-1"


def test_live_employee_caller_passes_the_company():
    """Guard at source: main.py must scope the call, or the fail-closed fix silently
    turns the endpoint into 'no policy, ever'."""
    with open(os.path.join(_REPO, "backend", "main.py"), encoding="utf-8") as fh:
        src = fh.read()
    i = src.index("db.get_published_hr_policy_for_employee(")
    call = src[i : src.index(")", src.index("country_code=country_code", i))]
    assert "company_entity=" in call, (
        "the live caller must pass company_entity; without it the query is scoped to "
        "nothing and the endpoint returns no policy for everyone."
    )
