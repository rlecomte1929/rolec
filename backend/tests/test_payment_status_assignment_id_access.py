"""AIQ-1687 — /api/payment/status on an assignment-id URL: resolves, but only for the owner.

The roadmap paywall had two fail-opens on the assignment-id URL form
(`/employee/case/{case_assignments.id}/roadmap` — also the Stripe checkout
`success_url`). `resolve_entitlement`'s was closed in #1652; `require_case_access`'
was closed by widening `get_assignment_by_case_id` to match the assignment's own id.
The failure shape: the lookup returns None → an employee gets 404 → the frontend
`fetchRoadmapUnlocked()` swallows the error and returns `unlocked=true` → an unpaid
free case sees the roadmap.

`test_get_assignment_by_case_id.py` pins the SQL. This pins the two properties that
matter at the edge, and that the SQL test cannot see:
  * the endpoint answers 200 `roadmap_unlocked=false` (NOT 404) for an assignment-id
    URL on an unpaid free case, and
  * widening RESOLUTION did not widen AUTHORIZATION — a non-owning employee is still
    refused, by assignment id and by case id alike.

The real `require_case_access` / `require_assignment_visibility` run here; only the
entitlement row and the paywall flag are stubbed.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from backend.app import auth_deps
from backend.app.auth_deps import require_hr_or_employee
from backend.app.routers import payment as payment_mod

# backend.database (the `db` singleton auth_deps uses) is a MagicMock under the test
# harness (backend/conftest.py) — a mock resolves everything and would hide both the
# 404 and the authorization check. Drive the REAL mixins against sqlite instead.
from backend.db.cases import CasesMixin
from backend.db.misc import MiscMixin

OWNER = "emp-1"
STRANGER = "emp-2"
ASSIGNMENT_ID = "assign-1"      # mirrors prod: the assignment id DIFFERS from the case id
CASE_ID = "case-1"


class _RealDB(MiscMixin, CasesMixin):
    def __init__(self, engine):
        self.engine = engine
        self._initialized = True  # skip init_db() in _exec
        self._init_lock = threading.Lock()


@pytest.fixture
def real_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as c:
        c.execute(text(
            "CREATE TABLE case_assignments (id TEXT, case_id TEXT, canonical_case_id TEXT, "
            "employee_user_id TEXT, hr_user_id TEXT, archived_at TEXT)"
        ))
        # Empty wizard_cases so coalesce_case_lookup_id is a clean no-op (matches a prod
        # case with no wizard row) rather than swallowing a missing-table exception.
        c.execute(text("CREATE TABLE wizard_cases (id TEXT)"))
        c.execute(
            text(
                "INSERT INTO case_assignments VALUES "
                "(:aid, :cid, :cid, :owner, 'hr-1', NULL)"
            ),
            {"aid": ASSIGNMENT_ID, "cid": CASE_ID, "owner": OWNER},
        )
    return _RealDB(engine)


def _client(monkeypatch, real_db, caller_id):
    monkeypatch.setattr(auth_deps, "db", real_db)
    # Paywall ON over an unpaid free case — the exact state where a 404 fail-open leaks
    # the €800 roadmap. Only the entitlement read is stubbed; access control is real.
    # `available=True` = the store answered; the row just isn't paid (AIQ-1699 shape).
    from backend.app.services.roadmap_entitlement import EntitlementLookup
    monkeypatch.setattr(
        payment_mod, "lookup_entitlement",
        lambda cid: EntitlementLookup({"access_tier": "free", "payment_status": "unpaid"}, True),
    )
    monkeypatch.setenv("RELOPASS_ROADMAP_PAYWALL_ENABLED", "true")

    app = FastAPI()
    app.include_router(payment_mod.router)
    # Role is UPPERCASE in a real session (UserRole.EMPLOYEE.value == "EMPLOYEE") — the
    # visibility check compares it exactly, so a lowercase stub would route an employee
    # down the HR branch and pass for the wrong reason.
    app.dependency_overrides[require_hr_or_employee] = lambda: {"id": caller_id, "role": "EMPLOYEE"}
    return TestClient(app)


def test_assignment_id_url_reports_locked_not_404(monkeypatch, real_db):
    # THE REGRESSION: before the fix this 404'd, and the frontend turned that into
    # "unlocked". It must report the real entitlement instead.
    r = _client(monkeypatch, real_db, OWNER).get(f"/api/payment/status/{ASSIGNMENT_ID}")
    assert r.status_code == 200, "assignment-id URL must resolve — a 404 here fails the paywall OPEN"
    body = r.json()
    assert body["access_tier"] == "free"
    assert body["roadmap_unlocked"] is False


def test_case_id_url_still_reports_locked(monkeypatch, real_db):
    # No regression for the id form that already worked.
    r = _client(monkeypatch, real_db, OWNER).get(f"/api/payment/status/{CASE_ID}")
    assert r.status_code == 200
    assert r.json()["roadmap_unlocked"] is False


@pytest.mark.parametrize("lookup_id", [ASSIGNMENT_ID, CASE_ID])
def test_non_owner_employee_is_refused(monkeypatch, real_db, lookup_id):
    # Widening RESOLUTION must not widen AUTHORIZATION. require_assignment_visibility
    # still gates on employee_user_id, so a stranger is refused by either id form —
    # this is the guard that would fail if someone dropped that tail check.
    r = _client(monkeypatch, real_db, STRANGER).get(f"/api/payment/status/{lookup_id}")
    assert r.status_code in (403, 404), "a non-owning employee must not read another case's entitlement"
    assert "roadmap_unlocked" not in r.text


def test_unknown_id_is_still_404(monkeypatch, real_db):
    # Resolution widened to the assignment id — not to everything.
    r = _client(monkeypatch, real_db, OWNER).get("/api/payment/status/does-not-exist")
    assert r.status_code == 404
