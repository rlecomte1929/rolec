"""AIQ-1731 — POST /api/hr/cases/{case_id}/assign must not mint a duplicate on retry.

The endpoint dispatches creation to a thread pool and gives up after 8s with
`503 "Assignment creation timed out. Please retry in a moment."`. The future is never
cancelled, so the row still commits — and the retry the copy explicitly asks for used to
create a SECOND `case_assignments` row carrying an identical `canonical_case_id`.

That is a live generator for one of the duplicate groups inventoried in
`docs/architecture/CASE_ID_UNIFICATION_AUDIT.md` (`7181b3a4…`: the same employee twice
plus a NULL-employee row, <70s apart). AIQ-1731's data cleanup is deferred; this closes
the source so the bucket stops refilling.

Two layers:
  * the lookup itself (`get_active_assignment_for_case_employee`) — matched forms,
    case-insensitivity, terminal-status and sentinel exclusions, recency ordering;
  * the endpoint — a double submit yields exactly ONE row, while two *different*
    employees on one case still legitimately yield two.

`backend/conftest.py` makes `backend.database.db` a MagicMock, which would resolve
everything and hide the duplicate entirely — so the real mixins run against sqlite here,
mirroring `test_payment_status_assignment_id_access.py`.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import threading
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from backend.db.cases import CasesMixin
from backend.db.misc import MiscMixin

CASE_ID = "case-1"
CANONICAL = "case-1"
COMPANY_ID = "co-1"
HR_ID = "hr-1"
EMPLOYEE = "adrien.martin@globaltech-demo.com"
OTHER_EMPLOYEE = "celine.dupont@meridian-demo.com"

_ASSIGNMENT_COLS = (
    "id TEXT, case_id TEXT, canonical_case_id TEXT, hr_user_id TEXT, employee_user_id TEXT, "
    "employee_identifier TEXT, status TEXT, employee_first_name TEXT, employee_last_name TEXT, "
    "employee_contact_id TEXT, employee_link_mode TEXT, created_at TEXT, updated_at TEXT, "
    "archived_at TEXT"
)


class _RealDB(MiscMixin, CasesMixin):
    """Real CasesMixin SQL over sqlite, with the non-case collaborators assign_case
    touches stubbed. Only the assignment write path is exercised for real."""

    def __init__(self, engine):
        self.engine = engine
        self._initialized = True  # skip init_db() in _exec
        self._init_lock = threading.Lock()

    # --- collaborators assign_case calls that are not under test -----------------
    def get_case_by_id(self, case_id, request_id=None):
        return {"id": case_id, "company_id": COMPANY_ID, "hr_user_id": HR_ID,
                "employee_id": None, "status": "active", "stage": None,
                "host_country": None, "home_country": None}

    def get_user_by_identifier(self, identifier, request_id=None):
        return None  # forces the pending-claim-invite path, as in prod for a new hire

    def get_profile_by_email(self, email):
        return None

    def resolve_or_create_employee_contact(self, company_id, raw, **kw):
        return "contact-1"

    def ensure_pending_assignment_invites(self, aid, case_id, hr_user_id, ecid,
                                          stored_identifier, en, request_id=None):
        return f"token-for-{aid}"

    def get_pending_claim_invite_token_for_assignment(self, assignment_id):
        return f"token-for-{assignment_id}"


def _engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as c:
        c.execute(text(f"CREATE TABLE case_assignments ({_ASSIGNMENT_COLS})"))
        c.execute(text("CREATE TABLE wizard_cases (id TEXT)"))
    return engine


@pytest.fixture
def real_db():
    return _RealDB(_engine())


def _insert(db, *, aid, case_id=CASE_ID, canonical=CANONICAL, identifier=EMPLOYEE,
            status="assigned", created_at="2026-07-01T00:00:00"):
    with db.engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO case_assignments (id, case_id, canonical_case_id, hr_user_id, "
                "employee_identifier, status, created_at) "
                "VALUES (:id, :cid, :can, :hr, :ident, :st, :ca)"
            ),
            {"id": aid, "cid": case_id, "can": canonical, "hr": HR_ID,
             "ident": identifier, "st": status, "ca": created_at},
        )


def _rows(db):
    with db.engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(
            text("SELECT id, canonical_case_id, employee_identifier FROM case_assignments")
        )]


# --------------------------------------------------------------------------------
# the lookup
# --------------------------------------------------------------------------------

class TestActiveAssignmentLookup:
    def test_matches_on_case_id(self, real_db):
        _insert(real_db, aid="a1")
        assert real_db.get_active_assignment_for_case_employee(CASE_ID, EMPLOYEE)["id"] == "a1"

    def test_matches_on_canonical_case_id(self, real_db):
        # canonical differs from case_id — the legacy shape the audit found in prod
        _insert(real_db, aid="a1", case_id="other-key", canonical=CASE_ID)
        assert real_db.get_active_assignment_for_case_employee(CASE_ID, EMPLOYEE)["id"] == "a1"

    def test_identifier_match_is_case_insensitive(self, real_db):
        # rows written before normalize_invite_key lower-cased the stored value
        _insert(real_db, aid="a1", identifier="Adrien.Martin@GlobalTech-Demo.com")
        assert real_db.get_active_assignment_for_case_employee(CASE_ID, EMPLOYEE)["id"] == "a1"

    def test_different_employee_is_not_a_match(self, real_db):
        """The guard must not collapse a genuine second assignment on the same case."""
        _insert(real_db, aid="a1", identifier=OTHER_EMPLOYEE)
        assert real_db.get_active_assignment_for_case_employee(CASE_ID, EMPLOYEE) is None

    @pytest.mark.parametrize("status", ["rejected", "closed"])
    def test_terminal_assignment_does_not_block_a_new_one(self, real_db, status):
        _insert(real_db, aid="a1", status=status)
        assert real_db.get_active_assignment_for_case_employee(CASE_ID, EMPLOYEE) is None

    def test_admin_created_sentinel_never_matches(self, real_db):
        """The sentinel is shared by every admin placeholder — collapsing on it would
        make the admin path unable to create more than one assignment."""
        _insert(real_db, aid="a1", identifier="admin-created")
        assert real_db.get_active_assignment_for_case_employee(CASE_ID, "admin-created") is None

    def test_returns_most_recent_match(self, real_db):
        _insert(real_db, aid="old", created_at="2026-07-01T00:00:00")
        _insert(real_db, aid="new", created_at="2026-07-20T00:00:00")
        assert real_db.get_active_assignment_for_case_employee(CASE_ID, EMPLOYEE)["id"] == "new"

    def test_unknown_case_or_blank_identifier_is_none(self, real_db):
        _insert(real_db, aid="a1")
        assert real_db.get_active_assignment_for_case_employee("nope", EMPLOYEE) is None
        assert real_db.get_active_assignment_for_case_employee(CASE_ID, "") is None


# --------------------------------------------------------------------------------
# the endpoint
# --------------------------------------------------------------------------------

@pytest.fixture
def assign(monkeypatch, real_db):
    """assign_case wired to the sqlite-backed db, with only the out-of-band side
    effects neutralised. The creation path — including db.create_assignment — is real."""
    from backend import main as main_mod

    monkeypatch.setattr(main_mod, "db", real_db)
    monkeypatch.setattr(main_mod, "_get_hr_company_id", lambda eff: COMPANY_ID)
    monkeypatch.setattr(main_mod, "_dispatch_hr_assign_side_effects", lambda **kw: None)
    monkeypatch.setattr(main_mod, "track_event", lambda *a, **kw: None)
    monkeypatch.setattr(main_mod, "_assign_invite_will_send", lambda ident: False)

    def _call(identifier=EMPLOYEE):
        request = SimpleNamespace(
            employeeIdentifier=identifier,
            employeeFirstName=None,
            employeeLastName=None,
            employeeLevel=None,
        )
        request_obj = SimpleNamespace(state=SimpleNamespace(request_id="req-1"))
        user = {"id": HR_ID, "role": "HR", "is_admin": False}
        return main_mod.assign_case(CASE_ID, request, request_obj, user)

    return _call


class TestAssignCaseIdempotency:
    def test_double_submit_creates_exactly_one_assignment(self, assign, real_db):
        """The regression: the 503 copy tells the user to retry, and the abandoned
        future already committed. The retry must reuse, not duplicate."""
        first = assign()
        second = assign()

        rows = _rows(real_db)
        assert len(rows) == 1, f"duplicate assignment created: {rows}"
        assert first.assignmentId == second.assignmentId
        # the whole point: one canonical_case_id, so UNIQUE(canonical_case_id) stays reachable
        assert len({r["canonical_case_id"] for r in rows}) == 1

    def test_retry_still_returns_the_invite_token(self, assign):
        """The first (timed-out) call never returned; the retry is what the HR user
        actually sees, so it must still carry a usable invite token."""
        second_token = assign() and assign().inviteToken
        assert second_token

    def test_two_different_employees_on_one_case_still_create_two(self, assign, real_db):
        """Regression guard: the guard is keyed on (case, employee), not on case alone."""
        a = assign(EMPLOYEE)
        b = assign(OTHER_EMPLOYEE)

        rows = _rows(real_db)
        assert len(rows) == 2, f"legitimate second assignment was suppressed: {rows}"
        assert a.assignmentId != b.assignmentId
