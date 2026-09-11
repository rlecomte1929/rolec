"""Visa Checklist reader — merge, persistence, and the two guards that matter.

Requirements come from `compute_case_requirements` (mocked here — this suite is about the
checklist layer, not the requirements engine). What is NOT mocked is the state table: it is
created in SQLite and exercised for real, because persistence across reads is the feature.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Set BEFORE any backend import. The query counter registers a `before_cursor_execute`
# listener at import time; importing a second app instance later re-registers it and raises
# "No such event 'before_cursor_execute'". Same preamble as test_test_drive_provision.py.
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.app.routers import case_requirement_checklist as router_mod  # noqa: E402
from backend.app.services import case_requirement_checklist as store  # noqa: E402

# Mirrors supabase/migrations/20261105000000_case_requirement_checklist_state.sql.
# requirement_id is TEXT there too — requirement_items.id is `character varying`.
SCHEMA = """
CREATE TABLE case_requirement_checklist_state (
    id             TEXT PRIMARY KEY,
    case_id        TEXT NOT NULL,
    requirement_id TEXT NOT NULL,
    completed      INTEGER NOT NULL DEFAULT 0,
    completed_by   TEXT,
    completed_at   TEXT,
    filing_status  TEXT,
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (case_id, requirement_id)
);
"""

CANONICAL_CASE_ID = "11111111-1111-4111-8111-111111111111"
OTHER_CASE_ID = "22222222-2222-4222-8222-222222222222"


def _requirement(rid: str, title: str, pillar: str = "RESIDENCE", **kw):
    return SimpleNamespace(
        id=rid, title=title, pillar=pillar,
        description=kw.get("description", ""), severity=kw.get("severity", "WARN"),
        owner=kw.get("owner", "EMPLOYEE"), nonObvious=kw.get("nonObvious"),
        timing=kw.get("timing"),
    )


def _computed(case_id=CANONICAL_CASE_ID, reqs=None, covered=True):
    return SimpleNamespace(
        caseId=case_id, destCountry="IRELAND", purpose="employment",
        covered=covered, requirements=reqs if reqs is not None else [
            _requirement("req-csep", "Critical Skills Employment Permit — eligibility",
                         nonObvious=True, timing="before travel"),
            _requirement("req-irp", "Stamp 1 / IRP registration", timing="within 90 days"),
            _requirement("req-tax", "Revenue registration", pillar="TAX"),
        ],
    )


class ChecklistFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            conn.execute(text(SCHEMA.strip().rstrip(";")))
        p = mock.patch.object(store.db, "engine", self.engine)
        p.start()
        self.addCleanup(p.stop)
        # SQLite in this fixture; make the module's cast switch agree.
        for attr, val in (("_CASE", ":case_id"), ("_ACTOR", ":actor_id"), ("_ID", ":id")):
            q = mock.patch.object(store, attr, val)
            q.start()
            self.addCleanup(q.stop)
        s = mock.patch.object(store, "_IS_SQLITE", True)
        s.start()
        self.addCleanup(s.stop)

        self.access = mock.patch.object(
            router_mod, "_assert_case_access", return_value=CANONICAL_CASE_ID
        )
        self.access_mock = self.access.start()
        self.addCleanup(self.access.stop)

        self.compute = mock.patch.object(
            router_mod, "compute_case_requirements", side_effect=lambda cid: _computed(cid)
        )
        self.compute_mock = self.compute.start()
        self.addCleanup(self.compute.stop)

        self.user = {"id": str(uuid.uuid4()), "role": "HR"}


class ChecklistReadTests(ChecklistFixture):
    def test_untouched_case_reads_all_incomplete(self) -> None:
        view = router_mod.get_checklist("assignment-id", user=self.user)
        self.assertEqual(view.totalCount, 3)
        self.assertEqual(view.completedCount, 0)
        self.assertEqual(view.percentComplete, 0)
        self.assertTrue(all(not i.completed for i in view.items))

    def test_carries_non_obvious_and_timing_through(self) -> None:
        view = router_mod.get_checklist("assignment-id", user=self.user)
        csep = next(i for i in view.items if i.id == "req-csep")
        self.assertIs(csep.nonObvious, True)
        self.assertEqual(csep.timing, "before travel")

    def test_filing_status_round_trips(self) -> None:
        router_mod.set_checklist_item(
            "assignment-id",
            router_mod.ChecklistToggle(
                requirement_id="req-irp", completed=True, filing_status="filed",
            ),
            user=self.user,
        )
        view = router_mod.get_checklist("assignment-id", user=self.user)
        irp = next(i for i in view.items if i.id == "req-irp")
        self.assertEqual(irp.filingStatus, "filed")
        self.assertTrue(irp.completed)

    def test_covered_false_is_distinct_from_an_empty_list(self) -> None:
        self.compute_mock.side_effect = lambda cid: _computed(cid, reqs=[], covered=False)
        view = router_mod.get_checklist("assignment-id", user=self.user)
        self.assertFalse(view.covered)
        self.assertEqual(view.totalCount, 0)
        self.assertEqual(view.percentComplete, 0)  # never a ZeroDivisionError


class ChecklistPersistenceTests(ChecklistFixture):
    def test_tick_persists_across_a_fresh_read(self) -> None:
        after_write = router_mod.set_checklist_item(
            "assignment-id",
            router_mod.ChecklistToggle(requirement_id="req-irp", completed=True),
            user=self.user,
        )
        self.assertEqual(after_write.completedCount, 1)
        self.assertEqual(after_write.percentComplete, 33)

        # The reload is the point: state must come from the table, not the response.
        reread = router_mod.get_checklist("assignment-id", user=self.user)
        irp = next(i for i in reread.items if i.id == "req-irp")
        self.assertTrue(irp.completed)
        self.assertIsNotNone(irp.completedAt)
        self.assertEqual(reread.completedCount, 1)

    def test_untick_clears_the_completion_stamp(self) -> None:
        router_mod.set_checklist_item(
            "assignment-id",
            router_mod.ChecklistToggle(requirement_id="req-irp", completed=True),
            user=self.user,
        )
        view = router_mod.set_checklist_item(
            "assignment-id",
            router_mod.ChecklistToggle(requirement_id="req-irp", completed=False),
            user=self.user,
        )
        irp = next(i for i in view.items if i.id == "req-irp")
        self.assertFalse(irp.completed)
        # A row must never read completed=false while still naming who completed it.
        self.assertIsNone(irp.completedAt)

    def test_toggling_twice_does_not_duplicate_rows(self) -> None:
        for _ in range(3):
            router_mod.set_checklist_item(
                "assignment-id",
                router_mod.ChecklistToggle(requirement_id="req-irp", completed=True),
                user=self.user,
            )
        with self.engine.begin() as conn:
            n = conn.execute(
                text("SELECT count(*) FROM case_requirement_checklist_state")
            ).scalar()
        self.assertEqual(n, 1)

    def test_percent_reaches_100_when_all_ticked(self) -> None:
        for rid in ("req-csep", "req-irp", "req-tax"):
            view = router_mod.set_checklist_item(
                "assignment-id",
                router_mod.ChecklistToggle(requirement_id=rid, completed=True),
                user=self.user,
            )
        self.assertEqual(view.percentComplete, 100)


class ChecklistGuardTests(ChecklistFixture):
    def test_sql_keys_on_the_resolved_id_not_the_path_param(self) -> None:
        """AIQ-1775: a route param is commonly an ASSIGNMENT id. Keying state on it writes
        rows the canonical read can never see, so the tick silently vanishes on reload."""
        router_mod.set_checklist_item(
            "some-assignment-id",
            router_mod.ChecklistToggle(requirement_id="req-irp", completed=True),
            user=self.user,
        )
        with self.engine.begin() as conn:
            stored = conn.execute(
                text("SELECT case_id FROM case_requirement_checklist_state")
            ).scalar()
        self.assertEqual(stored, CANONICAL_CASE_ID)
        self.assertNotEqual(stored, "some-assignment-id")

    def test_access_denial_propagates_and_writes_nothing(self) -> None:
        self.access_mock.side_effect = HTTPException(status_code=403, detail="Forbidden")
        with self.assertRaises(HTTPException) as ctx:
            router_mod.set_checklist_item(
                "another-companys-case",
                router_mod.ChecklistToggle(requirement_id="req-irp", completed=True),
                user=self.user,
            )
        self.assertEqual(ctx.exception.status_code, 403)
        with self.engine.begin() as conn:
            n = conn.execute(
                text("SELECT count(*) FROM case_requirement_checklist_state")
            ).scalar()
        self.assertEqual(n, 0, "a denied caller must not leave state behind")

    def test_requirement_outside_this_case_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            router_mod.set_checklist_item(
                "assignment-id",
                router_mod.ChecklistToggle(requirement_id="req-not-mine", completed=True),
                user=self.user,
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_state_does_not_bleed_between_cases(self) -> None:
        router_mod.set_checklist_item(
            "assignment-id",
            router_mod.ChecklistToggle(requirement_id="req-irp", completed=True),
            user=self.user,
        )
        # A different case resolves to a different canonical id; its checklist is untouched.
        self.access_mock.return_value = OTHER_CASE_ID
        other = router_mod.get_checklist("other-assignment", user=self.user)
        self.assertEqual(other.completedCount, 0)
        self.assertTrue(all(not i.completed for i in other.items))


class ChecklistRouteRegistrationTests(unittest.TestCase):
    """Registered in BOTH apps. Render boots backend.main; a router wired only into
    backend.app.main 405s in production (the AI-002 v2 incident)."""

    def test_route_registered_in_both_apps(self) -> None:
        # The module-level `app`, never create_app(): building a second app re-registers the
        # SQLAlchemy engine events and dies with "No such event 'before_cursor_execute'".
        # Same import shape as test_test_drive_provision.py.
        from backend.app.main import app as modular_app
        from backend.main import app as prod_app

        path = "/api/cases/{case_id}/requirements/checklist"
        for a, label in ((prod_app, "backend.main"), (modular_app, "backend.app.main")):
            self.assertIn(
                path, {r.path for r in a.routes}, f"checklist route missing in {label}"
            )


if __name__ == "__main__":
    unittest.main()
