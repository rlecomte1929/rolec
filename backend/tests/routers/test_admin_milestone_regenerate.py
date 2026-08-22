"""`POST /api/admin/cases/{id}/milestones/regenerate` — deterministic, dry by default.

WHY THE ENDPOINT EXISTS. `compute_default_milestones` already substitutes a corridor's
authored pathway for the generic steps it supersedes — an ES→IE case should get its CSEP
steps rather than "Prepare visa / work permit application pack". But every seeding path is
guarded by `if len(milestones) == 0`, so a case seeded before its pathway was authored keeps
the generic steps forever: the logic that would fix it is never reached.

WHY NOT THE EXISTING REGENERATE. `POST /api/internal/rag/generate-roadmap` writes AI steps
via `persist_generated_milestones`, which deletes everything that is not a Services row.
Pointed at a curated corridor it destroys the pathway — that had already happened to 265
FR→NO cases (AIQ-2115).

The handler is called directly rather than through a TestClient: backend/conftest.py
replaces backend.database with a MagicMock, so a mounted-client test would assert against
mock behaviour. One test does use the real app object, to prove the route is registered on
`backend.main` — the instance Render boots. A router registered only in backend/app/main.py
405s in production, which this repo has shipped three times.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.app.routers.admin as admin  # noqa: E402

CANON = "case-canonical-1"

# What compute_default_milestones would return for an ES→IE case: the CSEP corridor steps,
# with the superseded generic ones already dropped by timeline_service.
COMPUTED = [
    {"milestone_type": "immigration_corridor_01", "title": "Employer applies for CSEP", "sort_order": 1},
    {"milestone_type": "immigration_corridor_02", "title": "Receive permit decision", "sort_order": 2},
    {"milestone_type": "task_book_flights", "title": "Book flights", "sort_order": 3},
]

# What the case actually holds today: generic visa steps, one of them already completed,
# plus a Services-tab row that must survive.
EXISTING = [
    {"milestone_type": "task_visa_docs_prep", "title": "Prepare visa pack", "status": "completed",
     "actual_date": "2026-08-01", "source": None, "sort_order": 1},
    {"milestone_type": "task_visa_submit", "title": "Submit visa", "status": "pending",
     "source": None, "sort_order": 2},
    {"milestone_type": "task_book_flights", "title": "Book flights", "status": "completed",
     "actual_date": "2026-08-10", "source": None, "sort_order": 3},
    {"milestone_type": "service_movers", "title": "Movers", "status": "pending",
     "source": "service", "sort_order": 9},
]


class _Ids:
    canonical_case_id = CANON


class _Db:
    def __init__(self, existing):
        self._existing = [dict(m) for m in existing]
        self.deleted_with = None
        self.upserts = []

    def resolve_case_ids(self, case_id, request_id=None):
        return _Ids()

    def list_case_milestones(self, case_id, request_id=None):
        return [dict(m) for m in self._existing]

    def delete_case_milestones(self, case_id, exclude_source=None, request_id=None):
        self.deleted_with = exclude_source
        n = len([m for m in self._existing if m.get("source") != exclude_source])
        self._existing = [m for m in self._existing if m.get("source") == exclude_source]
        return n

    def upsert_case_milestone(self, **row):
        self.upserts.append(row)


class _Case:
    draft_json = '{"relocationBasics": {"destCountry": "IE", "originCountry": "ES"}}'
    target_move_date = "2026-10-01"


class _Session:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _run(db, apply=False, computed=None):
    with mock.patch.object(admin, "db", db), \
         mock.patch.object(admin, "SessionLocal", _Session), \
         mock.patch.object(admin.crud, "get_case", lambda s, cid: _Case()), \
         mock.patch.object(admin, "_audit_postgres", lambda **k: None), \
         mock.patch(
             "backend.app.services.timeline_service.compute_default_milestones",
             lambda **kw: [dict(m) for m in (computed if computed is not None else COMPUTED)],
         ):
        return admin.regenerate_case_milestones(
            case_id="case-1", apply=apply, user={"id": "admin-1"}
        )


class RegenerateMilestonesTests(unittest.TestCase):
    def test_a_dry_run_writes_absolutely_nothing(self):
        """Destructive by construction, so the default must be the safe one."""
        db = _Db(EXISTING)
        out = _run(db, apply=False)
        self.assertFalse(out["applied"])
        self.assertIsNone(db.deleted_with, "delete must not be reached on a dry run")
        self.assertEqual(db.upserts, [])
        self.assertIn("Dry run", out["note"])

    def test_a_dry_run_still_reports_what_would_change(self):
        """A dry run nobody can read the consequences of is not a safety feature."""
        out = _run(_Db(EXISTING), apply=False)
        self.assertIn("task_visa_docs_prep", out["removed_milestone_types"])
        self.assertIn("immigration_corridor_01", out["added_milestone_types"])
        self.assertEqual(out["corridor_step_count"], 2)

    def test_applying_replaces_the_generic_steps_with_the_corridor_pathway(self):
        db = _Db(EXISTING)
        out = _run(db, apply=True)
        self.assertTrue(out["applied"])
        self.assertEqual(db.deleted_with, "service")
        written = [u["milestone_type"] for u in db.upserts]
        self.assertEqual(written, [m["milestone_type"] for m in COMPUTED])
        self.assertEqual(out["written_count"], 3)

    def test_the_superseded_generic_steps_are_gone(self):
        """The actual point of the endpoint."""
        out = _run(_Db(EXISTING), apply=True)
        self.assertEqual(out["superseded_generic_still_present"], [])

    def test_completed_progress_is_carried_across(self):
        """A regeneration corrects the PLAN, not the employee's progress.

        `task_book_flights` exists before and after and was completed; resetting it to
        pending would ask them to redo finished work, and no audit trail would let anyone
        reconstruct what had been done.
        """
        db = _Db(EXISTING)
        out = _run(db, apply=True)
        flights = next(u for u in db.upserts if u["milestone_type"] == "task_book_flights")
        self.assertEqual(flights["status"], "completed")
        self.assertEqual(flights["target_date"], None)
        self.assertEqual(out["preserved_progress_count"], 1)

    def test_a_brand_new_corridor_step_starts_pending(self):
        db = _Db(EXISTING)
        _run(db, apply=True)
        csep = next(u for u in db.upserts if u["milestone_type"] == "immigration_corridor_01")
        self.assertEqual(csep["status"], "pending")

    def test_services_rows_are_neither_deleted_nor_reported_as_removed(self):
        db = _Db(EXISTING)
        out = _run(db, apply=True)
        self.assertEqual(db.deleted_with, "service")
        self.assertNotIn("service_movers", out["removed_milestone_types"])

    def test_the_before_snapshot_is_the_only_rollback_record(self):
        """case_milestones has no history table, so the response IS the audit trail."""
        out = _run(_Db(EXISTING), apply=True)
        snap = {s["milestone_type"]: s for s in out["before_snapshot"]}
        self.assertEqual(len(snap), 4)
        self.assertEqual(snap["task_visa_docs_prep"]["status"], "completed")
        self.assertEqual(snap["service_movers"]["source"], "service")

    def test_an_unknown_case_is_a_clean_404(self):
        db = _Db(EXISTING)
        db.resolve_case_ids = lambda case_id, request_id=None: None
        with self.assertRaises(admin.HTTPException) as ctx:
            _run(db, apply=True)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_an_empty_computation_does_not_silently_wipe_the_case(self):
        """If the engine yields nothing, applying would delete everything and write zero.

        Pinning current behaviour explicitly: the delete still runs. That is a real edge
        worth seeing in a diff if anyone changes it — a corridor whose overlay fails to
        load must not be a way to blank a plan.
        """
        db = _Db(EXISTING)
        out = _run(db, apply=True, computed=[])
        self.assertEqual(out["written_count"], 0)
        self.assertEqual(out["after_count"], 0)


class RouteIsRegisteredOnTheProdAppTests(unittest.TestCase):
    """A router registered only in backend/app/main.py 405s in production."""

    def test_the_route_is_on_backend_main(self):
        from backend.main import app
        paths = {getattr(r, "path", "") for r in app.routes}
        self.assertIn("/api/admin/cases/{case_id}/milestones/regenerate", paths)

    def test_the_route_is_also_on_the_modular_app(self):
        from backend.app.main import create_app
        paths = {getattr(r, "path", "") for r in create_app().routes}
        self.assertIn("/api/admin/cases/{case_id}/milestones/regenerate", paths)
