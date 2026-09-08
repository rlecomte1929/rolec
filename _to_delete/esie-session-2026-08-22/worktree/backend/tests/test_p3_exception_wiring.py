"""
test_p3_exception_wiring.py — P3: Exception request DB layer and end-to-end wiring tests.

Covers:
  DB layer (SQLite in-memory):
    - upsert_exception_request() creates a row and returns it
    - Re-running upsert with same (case_id, exception_type, status=pending) updates, not duplicates
    - Rows with resolved status are not overwritten — new row inserted alongside
    - list_exception_requests() returns blockers before warnings
    - list_exception_requests() filters by assignment_id when supplied
    - list_exception_requests() returns [] for unknown case_id

  End-to-end: exception flags from compute_default_milestones context (no DB required)
    - Oliver (German → US, LTA) profile produces tenure_insufficient + no_sponsoring_entity flags
    - EU free-movement profile produces no exception flags
    - Domestic profile produces no exception flags
    - Cost threshold fires independently of regime

  Route response shape (tested via dict construction, no HTTP stack needed)
    - blockers/warnings grouping is correct
    - status filter works
    - total count is accurate
"""
from __future__ import annotations

import sys
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List

import tempfile
import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ── Point DATABASE_URL at a temp SQLite file BEFORE backend.database is imported.
# database.py captures DATABASE_URL at module load time, so this must come first.
_TEST_DB_FILE = os.path.join(tempfile.gettempdir(), "test_p3_exception_wiring.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB_FILE}")

from backend.app.services.immigration_regime import ImmigrationRegimeRouter
from backend.app.services.exception_request_service import ExceptionRequestService, ExceptionFlag


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

router = ImmigrationRegimeRouter()
svc = ExceptionRequestService()

# [AIQ-1392] Real-DB fixture for the exception-request DB layer.
# backend/conftest.py globally mocks backend.database (sys.modules.setdefault) so unit
# tests don't need a live DB — but that makes _make_sqlite_db() return a MagicMock, so the
# DB-layer tests below never actually persist. This fixture imports the REAL backend.database
# once against a temp SQLite file, creates the one standalone table (exception_requests) it
# needs directly — init_db is neither called nor needed: upsert generates id + timestamps in
# Python — and swaps that real module into sys.modules only for the duration of a DB-layer
# test, restoring the conftest mock on teardown so it never leaks to tests that expect it.
_EXCEPTION_REQUESTS_SQLITE_DDL = """
CREATE TABLE exception_requests (
    id                 TEXT PRIMARY KEY,
    case_id            TEXT NOT NULL,
    assignment_id      TEXT,
    exception_type     TEXT NOT NULL,
    reason             TEXT NOT NULL,
    severity           TEXT NOT NULL DEFAULT 'warning',
    status             TEXT NOT NULL DEFAULT 'pending',
    recommended_action TEXT,
    resolved_at        TEXT,
    resolved_by        TEXT,
    resolution_notes   TEXT,
    created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


_real_db_module = None  # cached real (sqlite-backed) backend.database, loaded under a private name
_active_real_db = None  # the live real Database while a real_exception_db test runs; else None


def _load_real_backend_database():
    """Load the REAL backend/database.py under a PRIVATE module name (never touching the
    conftest `backend.database` mock in sys.modules) against the temp-sqlite DATABASE_URL, and
    create the one standalone table it needs. `init_db` is neither called nor needed — upsert
    generates id + timestamps in Python. Cached; returns the loaded module."""
    global _real_db_module
    if _real_db_module is not None:
        return _real_db_module
    import importlib.util
    from sqlalchemy import text

    os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_FILE}"
    path = os.path.join(_REPO_ROOT, "backend", "database.py")
    # Private name → the mock at sys.modules['backend.database'] stays intact for every other
    # test. __package__='backend' makes database.py's `from .db_config` / `from .db.support`
    # relative imports resolve to the real (never-mocked) modules.
    spec = importlib.util.spec_from_file_location("backend._real_database_for_tests", path)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "backend"
    spec.loader.exec_module(mod)  # runs `_engine = create_engine(sqlite)` + `db = Database()`
    with mod.db.engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS exception_requests"))
        conn.execute(text(_EXCEPTION_REQUESTS_SQLITE_DDL))
    _real_db_module = mod
    return mod


@pytest.fixture
def real_exception_db():
    """Activate the real sqlite-backed Database for one DB-layer test; restore isolation after.
    Does NOT modify sys.modules['backend.database'] — `_make_sqlite_db()` reads `_active_real_db`."""
    global _active_real_db
    from sqlalchemy import text

    mod = _load_real_backend_database()
    with mod.db.engine.begin() as conn:
        conn.execute(text("DELETE FROM exception_requests"))  # per-test isolation
    _active_real_db = mod.db
    try:
        yield mod.db
    finally:
        _active_real_db = None


def _make_sqlite_db():
    """Return the real SQLite-backed Database (only inside the real_exception_db fixture)."""
    if _active_real_db is not None:
        return _active_real_db
    from backend.database import Database  # fallback: outside the fixture (returns the mock)
    return Database()


def _case_id():
    return f"test-{uuid.uuid4().hex[:8]}"


def _flag_types(flags: List[ExceptionFlag]) -> List[str]:
    return [f.exception_type for f in flags]


# ─────────────────────────────────────────────────────────────────────────────
# 1. DB layer — upsert_exception_request
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.usefixtures("real_exception_db")
class TestUpsertExceptionRequest:

    def test_insert_creates_row(self):
        db = _make_sqlite_db()
        cid = _case_id()
        row = db.upsert_exception_request(
            case_id=cid,
            exception_type="tenure_insufficient",
            reason="Employee has only 8 months tenure.",
            severity="blocker",
            recommended_action="Delay move date.",
        )
        assert row["case_id"] == cid
        assert row["exception_type"] == "tenure_insufficient"
        assert row["severity"] == "blocker"
        assert row["status"] == "pending"
        assert row["recommended_action"] == "Delay move date."
        assert row["id"]  # UUID assigned

    def test_idempotent_re_run_updates_not_duplicates(self):
        """Calling upsert twice with same (case_id, exception_type, pending) → 1 row."""
        db = _make_sqlite_db()
        cid = _case_id()
        db.upsert_exception_request(
            case_id=cid,
            exception_type="timeline_breach",
            reason="Original reason.",
            severity="warning",
        )
        db.upsert_exception_request(
            case_id=cid,
            exception_type="timeline_breach",
            reason="Updated reason.",
            severity="blocker",  # severity upgraded
        )
        rows = db.list_exception_requests(cid)
        timeline_rows = [r for r in rows if r["exception_type"] == "timeline_breach"]
        assert len(timeline_rows) == 1, "Should not duplicate pending rows on re-run"
        assert timeline_rows[0]["reason"] == "Updated reason."
        assert timeline_rows[0]["severity"] == "blocker"

    def test_resolved_row_not_overwritten_new_row_inserted(self):
        """A resolved (approved) row is preserved; a new pending row is created."""
        from sqlalchemy import text  # sqlalchemy is available since DB layer uses it
        db = _make_sqlite_db()
        cid = _case_id()
        # Insert initial pending flag
        row = db.upsert_exception_request(
            case_id=cid,
            exception_type="cost_threshold",
            reason="First time.",
            severity="warning",
        )
        # Manually resolve it to simulate HR approval
        with db.engine.begin() as conn:
            conn.execute(
                text("UPDATE exception_requests SET status='approved' WHERE id=:id"),
                {"id": row["id"]},
            )
        # Upsert again — should create a new pending row, not touch the approved one
        db.upsert_exception_request(
            case_id=cid,
            exception_type="cost_threshold",
            reason="Second time.",
            severity="warning",
        )
        rows = db.list_exception_requests(cid)
        cost_rows = [r for r in rows if r["exception_type"] == "cost_threshold"]
        assert len(cost_rows) == 2, "Approved row + new pending row should coexist"
        statuses = {r["status"] for r in cost_rows}
        assert "approved" in statuses
        assert "pending" in statuses

    def test_assignment_id_stored_and_filterable(self):
        db = _make_sqlite_db()
        cid = _case_id()
        aid = f"assign-{uuid.uuid4().hex[:8]}"
        db.upsert_exception_request(
            case_id=cid,
            exception_type="no_sponsoring_entity",
            reason="No US entity.",
            severity="blocker",
            assignment_id=aid,
        )
        rows = db.list_exception_requests(cid, assignment_id=aid)
        assert len(rows) == 1
        assert rows[0]["assignment_id"] == aid

    def test_different_exception_types_coexist(self):
        db = _make_sqlite_db()
        cid = _case_id()
        db.upsert_exception_request(cid, "tenure_insufficient", "r1", "blocker")
        db.upsert_exception_request(cid, "no_sponsoring_entity", "r2", "blocker")
        db.upsert_exception_request(cid, "timeline_breach", "r3", "warning")
        rows = db.list_exception_requests(cid)
        assert len(rows) == 3

    def test_row_has_timestamps(self):
        db = _make_sqlite_db()
        cid = _case_id()
        row = db.upsert_exception_request(cid, "cost_threshold", "reason", "warning")
        assert row.get("created_at")
        assert row.get("updated_at")


# ─────────────────────────────────────────────────────────────────────────────
# 2. DB layer — list_exception_requests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.usefixtures("real_exception_db")
class TestListExceptionRequests:

    def test_empty_for_unknown_case(self):
        db = _make_sqlite_db()
        rows = db.list_exception_requests("case-does-not-exist")
        assert rows == []

    def test_blockers_returned_before_warnings(self):
        db = _make_sqlite_db()
        cid = _case_id()
        db.upsert_exception_request(cid, "timeline_breach", "tight timeline", "warning")
        db.upsert_exception_request(cid, "tenure_insufficient", "not enough tenure", "blocker")
        db.upsert_exception_request(cid, "cost_threshold", "over budget", "warning")
        rows = db.list_exception_requests(cid)
        assert len(rows) == 3
        assert rows[0]["severity"] == "blocker", "Blocker must come first"
        # Warnings follow
        warning_rows = [r for r in rows if r["severity"] == "warning"]
        assert len(warning_rows) == 2

    def test_filters_by_assignment_id(self):
        db = _make_sqlite_db()
        cid = _case_id()
        aid = f"assign-{uuid.uuid4().hex[:8]}"
        db.upsert_exception_request(cid, "cost_threshold", "reason", "warning", assignment_id=aid)
        db.upsert_exception_request(cid, "tenure_insufficient", "reason", "blocker", assignment_id=None)
        # With assignment_id filter — only 1
        rows = db.list_exception_requests(cid, assignment_id=aid)
        assert len(rows) == 1
        assert rows[0]["exception_type"] == "cost_threshold"
        # Without filter — both
        all_rows = db.list_exception_requests(cid)
        assert len(all_rows) == 2

    def test_multiple_cases_isolated(self):
        """Flags for case A must not appear when querying case B."""
        db = _make_sqlite_db()
        cid_a = _case_id()
        cid_b = _case_id()
        db.upsert_exception_request(cid_a, "tenure_insufficient", "r", "blocker")
        rows_b = db.list_exception_requests(cid_b)
        assert rows_b == []


# ─────────────────────────────────────────────────────────────────────────────
# 3. End-to-end: ExceptionRequestService + ImmigrationRegimeRouter
# ─────────────────────────────────────────────────────────────────────────────

class TestE2EExceptionDetection:
    """
    Tests the full evaluation chain without a DB: regime detection → flag evaluation.
    Mirrors what the wired timeline call sites do.
    """

    def _evaluate(self, profile: Dict[str, Any]) -> List[ExceptionFlag]:
        regime = router.detect_regime(
            nationality=profile.get("nationality"),
            destination_country=profile.get("destination_country"),
            origin_country=profile.get("origin_country"),
            contract_type=profile.get("contract_type"),
        )
        return svc.evaluate_case(profile=profile, regime=regime)

    def test_oliver_profile_blockers_present(self):
        """Oliver (German, LTA → US): tenure + no entity → 2 blockers minimum."""
        flags = self._evaluate({
            "nationality": "German",
            "destination_country": "United States",
            "origin_country": "Germany",
            "contract_type": "lta",
            "employment_tenure_months": 8,       # < 12 → tenure_insufficient
            "us_entity_confirmed": False,         # → no_sponsoring_entity
            "weeks_to_move_date": 30,
        })
        types = _flag_types(flags)
        assert "tenure_insufficient" in types
        assert "no_sponsoring_entity" in types
        blockers = [f for f in flags if f.severity == "blocker"]
        assert len(blockers) >= 2

    def test_oliver_clean_profile_no_flags(self):
        flags = self._evaluate({
            "nationality": "German",
            "destination_country": "United States",
            "contract_type": "lta",
            "employment_tenure_months": 24,
            "us_entity_confirmed": True,
            "weeks_to_move_date": 30,
            "specialized_knowledge_documented": True,
        })
        assert flags == []

    def test_eu_free_movement_no_flags(self):
        flags = self._evaluate({
            "nationality": "France",
            "destination_country": "Netherlands",
            "origin_country": "France",
            "contract_type": "lta",
        })
        assert flags == []

    def test_domestic_no_flags(self):
        flags = self._evaluate({
            "destination_country": "France",
            "origin_country": "France",
            "contract_type": "lta",
        })
        assert flags == []

    def test_cost_threshold_fires_on_us_case(self):
        flags = self._evaluate({
            "nationality": "German",
            "destination_country": "United States",
            "contract_type": "lta",
            "employment_tenure_months": 24,
            "us_entity_confirmed": True,
            "weeks_to_move_date": 30,
            "specialized_knowledge_documented": True,
            "estimated_package_cost_usd": 200_000,
        })
        types = _flag_types(flags)
        assert "cost_threshold" in types

    def test_yuki_japan_missing_category_flag(self):
        flags = self._evaluate({
            "nationality": "Japanese",
            "destination_country": "Japan",
            "origin_country": "France",
            "contract_type": "lta",
            "weeks_to_move_date": 20,
            # no japan_visa_category → role_category_ambiguous
        })
        types = _flag_types(flags)
        assert "role_category_ambiguous" in types

    @pytest.mark.usefixtures("real_exception_db")
    def test_flags_then_stored_in_db(self):
        """Simulate what the wired call site does: detect flags and persist them."""
        db = _make_sqlite_db()
        cid = _case_id()
        profile = {
            "nationality": "German",
            "destination_country": "United States",
            "contract_type": "lta",
            "employment_tenure_months": 8,
            "us_entity_confirmed": False,
            "weeks_to_move_date": 30,
            "specialized_knowledge_documented": True,
        }
        flags = self._evaluate(profile)
        assert len(flags) >= 2
        for flag in flags:
            db.upsert_exception_request(
                case_id=cid,
                exception_type=flag.exception_type,
                reason=flag.reason,
                severity=flag.severity,
                recommended_action=flag.recommended_action or None,
            )
        rows = db.list_exception_requests(cid)
        stored_types = {r["exception_type"] for r in rows}
        assert "tenure_insufficient" in stored_types
        assert "no_sponsoring_entity" in stored_types

    @pytest.mark.usefixtures("real_exception_db")
    def test_re_running_detection_does_not_duplicate_rows(self):
        """Running detection twice (e.g. timeline called twice) leaves exactly 1 row per type."""
        db = _make_sqlite_db()
        cid = _case_id()
        profile = {
            "nationality": "German",
            "destination_country": "United States",
            "contract_type": "lta",
            "employment_tenure_months": 8,
            "us_entity_confirmed": False,
        }
        for _ in range(3):  # simulated 3 timeline refreshes
            flags = self._evaluate(profile)
            for flag in flags:
                db.upsert_exception_request(
                    case_id=cid,
                    exception_type=flag.exception_type,
                    reason=flag.reason,
                    severity=flag.severity,
                )
        rows = db.list_exception_requests(cid)
        types = [r["exception_type"] for r in rows]
        assert len(types) == len(set(types)), "No duplicate rows after multiple detection runs"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Route response shape (logic-only, no HTTP stack)
# ─────────────────────────────────────────────────────────────────────────────

class TestExceptionsRouteShape:
    """
    Tests the grouping logic that the route applies to DB results.
    Mirrors list_case_exceptions() without importing FastAPI.
    """

    def _group_flags(self, flags: List[Dict], status_filter=None):
        """Mirror the route's grouping logic."""
        if status_filter:
            flags = [f for f in flags if f.get("status") == status_filter]
        blockers = [f for f in flags if f.get("severity") == "blocker"]
        warnings = [f for f in flags if f.get("severity") == "warning"]
        return {
            "blockers": blockers,
            "warnings": warnings,
            "total": len(flags),
        }

    @pytest.mark.usefixtures("real_exception_db")
    def test_grouping_separates_correctly(self):
        db = _make_sqlite_db()
        cid = _case_id()
        db.upsert_exception_request(cid, "tenure_insufficient", "r", "blocker")
        db.upsert_exception_request(cid, "no_sponsoring_entity", "r", "blocker")
        db.upsert_exception_request(cid, "cost_threshold", "r", "warning")
        flags = db.list_exception_requests(cid)
        result = self._group_flags(flags)
        assert result["total"] == 3
        assert len(result["blockers"]) == 2
        assert len(result["warnings"]) == 1

    @pytest.mark.usefixtures("real_exception_db")
    def test_status_filter_pending_only(self):
        from sqlalchemy import text  # available; installed as DB layer dependency
        db = _make_sqlite_db()
        cid = _case_id()
        db.upsert_exception_request(cid, "cost_threshold", "r", "warning")
        # Manually approve
        row = db.upsert_exception_request(cid, "tenure_insufficient", "r", "blocker")
        with db.engine.begin() as conn:
            conn.execute(
                text("UPDATE exception_requests SET status='approved' WHERE id=:id"),
                {"id": row["id"]},
            )
        all_flags = db.list_exception_requests(cid)
        pending_result = self._group_flags(all_flags, status_filter="pending")
        assert pending_result["total"] == 1
        assert pending_result["warnings"][0]["exception_type"] == "cost_threshold"

    @pytest.mark.usefixtures("real_exception_db")
    def test_empty_case_returns_zeros(self):
        db = _make_sqlite_db()
        cid = _case_id()
        flags = db.list_exception_requests(cid)
        result = self._group_flags(flags)
        assert result == {"blockers": [], "warnings": [], "total": 0}

    @pytest.mark.usefixtures("real_exception_db")
    def test_blocker_only_case(self):
        db = _make_sqlite_db()
        cid = _case_id()
        db.upsert_exception_request(cid, "tenure_insufficient", "r", "blocker")
        flags = db.list_exception_requests(cid)
        result = self._group_flags(flags)
        assert result["total"] == 1
        assert len(result["blockers"]) == 1
        assert result["warnings"] == []
