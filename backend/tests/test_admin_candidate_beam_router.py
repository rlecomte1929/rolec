"""The admin review surface for the candidate beam.

App-mounted against `backend.main.app` — the app Render actually boots — because a router
registered only in the modular app returns 405 in production, and this repo has shipped
that exact bug three times. `require_admin` is overridden on the auth_deps object the
router depends on; overriding a different copy silently never fires.
"""
from __future__ import annotations

import os
import sys
import unittest
from typing import Any, Dict, List
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ["RELOPASS_DISABLE_RATE_LIMITS"] = "1"
os.environ["RELOPASS_QUERY_COUNTER_OFF"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

import backend.main as main  # noqa: E402
import backend.app.auth_deps as auth_deps  # noqa: E402
from backend.app.routers import admin_candidate_beam as beam_router  # noqa: E402

_ADMIN = {"id": "admin-1", "email": "admin@relopass.com", "role": "ADMIN"}

_ITEM = {
    "candidate_uid": "c1",
    "title": "Tax Exit from France",
    "official_guidance": "File form 2042.",
    "actual_reality": "Often asks for proof of departure.",
    "action_required": "File before leaving.",
    "source": "https://www.impots.gouv.fr/particulier/depart",
    "category": "tax",
    "status": "approved",
    "flagged": False,
    "pass_frequency": 4,
    "confidence_band": "strong",
}


class _Result:
    """Stands in for a SQLAlchemy result: .mappings().all() / .first()."""

    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows
        self.executed: List[Any] = []
        self.committed = False

    def execute(self, stmt, params=None):
        self.executed.append((str(stmt), params or {}))
        text = str(stmt)
        if text.strip().upper().startswith("UPDATE"):
            return _Result([])
        return _Result(self._rows)

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class AdminCandidateBeamRouterTests(unittest.TestCase):
    def setUp(self):
        main.app.dependency_overrides[auth_deps.require_admin] = lambda: dict(_ADMIN)
        self.addCleanup(main.app.dependency_overrides.clear)
        self.client = TestClient(main.app, raise_server_exceptions=False)
        self.session = _Session([dict(_ITEM)])
        patch = mock.patch.object(beam_router, "SessionLocal", lambda: self.session)
        patch.start()
        self.addCleanup(patch.stop)

    # ── the dual-registration rule ──────────────────────────────────────────

    def test_every_route_is_mounted_in_the_app_render_boots(self):
        paths = {r.path for r in main.app.routes if "candidate-beam" in r.path}
        self.assertEqual(len(paths), 7, f"expected 7 routes, got {sorted(paths)}")

    # ── auth ────────────────────────────────────────────────────────────────

    def test_the_queue_is_admin_only(self):
        """Unreviewed model output reads exactly like a published requirement."""
        main.app.dependency_overrides.clear()
        resp = TestClient(main.app, raise_server_exceptions=False).get(
            "/api/admin/candidate-beam/runs"
        )
        self.assertIn(resp.status_code, (401, 403), resp.text)

    # ── reads ───────────────────────────────────────────────────────────────

    def test_items_are_returned_with_counts(self):
        resp = self.client.get("/api/admin/candidate-beam/runs/abc/items")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["counts"]["total"], 1)
        self.assertEqual(body["counts"]["approved"], 1)

    def test_source_missing_is_its_own_number_not_buried_in_the_total(self):
        """It is the research worklist, not a defect — a reviewer has to be able to see
        how much of the run nobody sourced."""
        self.session._rows = [dict(_ITEM, source_missing=True, source=None)]
        resp = self.client.get("/api/admin/candidate-beam/runs/abc/items")
        self.assertEqual(resp.json()["counts"]["source_missing"], 1)

    def test_pillars_endpoint_exposes_the_canonical_vocabulary_and_the_grounded_map(self):
        resp = self.client.get("/api/admin/candidate-beam/pillars")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(len(body["pillars"]), 7)
        self.assertEqual(body["grounded_categories"]["tax"], "EMPLOYMENT")
        self.assertNotIn("pets", body["grounded_categories"])

    # ── review ──────────────────────────────────────────────────────────────

    def test_approving_a_candidate_records_who_and_when(self):
        self.session._rows = [{"status": "pending_review"}]
        resp = self.client.post(
            "/api/admin/candidate-beam/items/11111111-1111-4111-8111-111111111111/review",
            json={"status": "approved", "review_note": "checked the citation"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(self.session.committed)
        update = [sql for sql, _ in self.session.executed if sql.strip().upper().startswith("UPDATE")]
        self.assertTrue(update and "reviewed_by" in update[0])

    def test_an_already_imported_candidate_cannot_be_re_reviewed(self):
        """Its staged row is the record of that decision; flipping the queue afterwards
        would leave provenance and queue disagreeing, and the staged row is what a reader
        eventually sees."""
        self.session._rows = [{"status": "imported"}]
        resp = self.client.post(
            "/api/admin/candidate-beam/items/11111111-1111-4111-8111-111111111111/review",
            json={"status": "rejected"},
        )
        self.assertEqual(resp.status_code, 409, resp.text)

    def test_an_unknown_candidate_is_404_not_a_silent_no_op(self):
        self.session._rows = []
        resp = self.client.post(
            "/api/admin/candidate-beam/items/11111111-1111-4111-8111-111111111111/review",
            json={"status": "approved"},
        )
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_an_invalid_review_status_is_rejected_by_the_schema(self):
        resp = self.client.post(
            "/api/admin/candidate-beam/items/11111111-1111-4111-8111-111111111111/review",
            json={"status": "verified"},
        )
        self.assertEqual(resp.status_code, 422, resp.text)

    # ── import plan ─────────────────────────────────────────────────────────

    def test_import_plan_writes_nothing_and_says_so(self):
        resp = self.client.post(
            "/api/admin/candidate-beam/runs/abc/import-plan", json={"country": "FRANCE"}
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIs(body["written"], False)
        self.assertFalse(self.session.committed)
        self.assertEqual(body["importable"], 1)

    def test_import_plan_reports_the_unsourced_as_skips_with_reasons(self):
        self.session._rows = [dict(_ITEM, source=None)]
        body = self.client.post(
            "/api/admin/candidate-beam/runs/abc/import-plan", json={"country": "FRANCE"}
        ).json()
        self.assertEqual(body["importable"], 0)
        self.assertIn("no source", body["skipped"][0]["reason"])

    def test_import_plan_asks_for_a_pillar_it_cannot_ground(self):
        self.session._rows = [dict(_ITEM, category="pets")]
        body = self.client.post(
            "/api/admin/candidate-beam/runs/abc/import-plan", json={"country": "NORWAY"}
        ).json()
        self.assertEqual(body["importable"], 0)
        self.assertIn("pillar unresolved", body["skipped"][0]["reason"])

    def test_a_human_pillar_override_is_honoured(self):
        self.session._rows = [dict(_ITEM, category="pets")]
        body = self.client.post(
            "/api/admin/candidate-beam/runs/abc/import-plan",
            json={"country": "NORWAY", "pillar_overrides": {"c1": "TIMELINE"}},
        ).json()
        self.assertEqual(body["importable"], 1)
        self.assertEqual(body["pillar_by_uid"]["c1"], "TIMELINE")

    # ── the refusal that matters ────────────────────────────────────────────

    def test_there_is_no_promote_endpoint_on_this_router(self):
        """The beam must not be able to reach requirement_items from here. A promote
        button would retire the entire safety argument for the feature."""
        paths = " ".join(r.path for r in main.app.routes if "candidate-beam" in r.path)
        self.assertNotIn("promote", paths)

    def test_no_sql_in_this_router_targets_requirement_items(self):
        """Prose may DISCUSS requirement_items — the docstring explains why it is off
        limits. Executable SQL may not touch it. Checks the string literals the module
        actually executes, not its comments."""
        import ast
        import inspect

        tree = ast.parse(inspect.getsource(beam_router))
        literals = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        sql = [lit.lower() for lit in literals if "select " in lit.lower() or "update " in lit.lower()
               or "insert " in lit.lower()]
        offenders = [q for q in sql if "requirement_items" in q]
        self.assertEqual(offenders, [], f"router SQL touches requirement_items: {offenders}")

    def test_the_router_does_not_import_the_promoter(self):
        """crud.create_requirement_item is the promoter's writer. Importing it here would
        put a customer-facing write one call away from an unreviewed queue."""
        import inspect

        source = inspect.getsource(beam_router)
        self.assertNotIn("create_requirement_item", source)
        self.assertNotIn("from ..crud", source)


if __name__ == "__main__":
    unittest.main()
