"""Attaching a human-researched source to a candidate the beam could not cite.

App-mounted against `backend.main.app` for the same reason as the sibling router test: a
router registered only in the modular app 405s in production.

The assertions that matter are the refusals and the non-effects. Recording a URL is trivial;
the value is that doing so cannot overwrite the model's claim, cannot touch an imported row,
and cannot make anything look verified.
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
OFFICIAL = "https://www.udi.no/en/want-to-apply/registration-eu-eea/"
BLOG = "https://some-relocation-blog.example.com/moving"
SOURCE_URL = "/api/admin/candidate-beam/items/11111111-1111-1111-1111-111111111111/source"
REVIEW_URL = "/api/admin/candidate-beam/items/11111111-1111-1111-1111-111111111111/review"


class _Result:
    def __init__(self, rows):
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
        if str(stmt).strip().upper().startswith("UPDATE"):
            return _Result([])
        return _Result(self._rows)

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def updates(self):
        return [(sql, prm) for sql, prm in self.executed if sql.strip().upper().startswith("UPDATE")]


class BeamSourcingTests(unittest.TestCase):
    def setUp(self):
        main.app.dependency_overrides[auth_deps.require_admin] = lambda: dict(_ADMIN)
        self.addCleanup(main.app.dependency_overrides.clear)
        self.client = TestClient(main.app, raise_server_exceptions=False)
        self._install([{"status": "pending_review", "source": None, "researched_source_url": None}])

    def _install(self, rows):
        self.session = _Session([dict(r) for r in rows])
        patch = mock.patch.object(beam_router, "SessionLocal", lambda: self.session)
        patch.start()
        self.addCleanup(patch.stop)

    # ── auth ────────────────────────────────────────────────────────────────

    def test_attaching_a_source_is_admin_only(self):
        main.app.dependency_overrides.clear()
        resp = TestClient(main.app, raise_server_exceptions=False).post(
            SOURCE_URL, json={"source_url": OFFICIAL}
        )
        self.assertIn(resp.status_code, (401, 403), resp.text)

    # ── the happy path ──────────────────────────────────────────────────────

    def test_a_researched_source_is_stored_with_its_class_and_its_researcher(self):
        resp = self.client.post(SOURCE_URL, json={"source_url": OFFICIAL})
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["researched_source_class"], "official")
        self.assertEqual(body["researched_by"], "admin-1")

        sql, params = self.session.updates()[0]
        self.assertIn("researched_source_url", sql)
        self.assertEqual(params["url"], OFFICIAL)
        self.assertEqual(params["klass"], "official")

    def test_it_never_writes_the_models_claim_column(self):
        """`source` is the model's verbatim claim; a human's finding must not overwrite it,
        or the two provenances become indistinguishable on exactly the rows where the
        difference matters."""
        self.client.post(SOURCE_URL, json={"source_url": OFFICIAL})
        sql, _ = self.session.updates()[0]
        self.assertNotIn("SET source", sql)
        self.assertNotIn("source =", sql)

    def test_the_evidence_quote_a_person_read_is_kept(self):
        self.client.post(
            SOURCE_URL, json={"source_url": OFFICIAL, "evidence_quote": "Register within 3 months."}
        )
        _, params = self.session.updates()[0]
        self.assertEqual(params["quote"], "Register within 3 months.")

    def test_a_blank_quote_is_stored_as_null_not_as_empty_string(self):
        self.client.post(SOURCE_URL, json={"source_url": OFFICIAL, "evidence_quote": "   "})
        _, params = self.session.updates()[0]
        self.assertIsNone(params["quote"])

    # ── refusals ────────────────────────────────────────────────────────────

    def test_a_non_url_is_refused(self):
        for bad in ("not a url", "ftp://x.example.com/a", "www.udi.no/x"):
            resp = self.client.post(SOURCE_URL, json={"source_url": bad})
            self.assertEqual(resp.status_code, 422, f"{bad} -> {resp.text}")

    def test_an_unknown_candidate_is_404(self):
        self._install([])
        resp = self.client.post(SOURCE_URL, json={"source_url": OFFICIAL})
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_an_imported_candidate_is_frozen(self):
        """Its staged row already records the source it used; changing this one would leave
        the two disagreeing, and the staged row is what a reader eventually sees."""
        self._install([{"status": "imported", "source": None, "researched_source_url": None}])
        resp = self.client.post(SOURCE_URL, json={"source_url": OFFICIAL})
        self.assertEqual(resp.status_code, 409, resp.text)
        self.assertEqual(self.session.updates(), [])

    def test_an_unofficial_source_is_recorded_rather_than_refused(self):
        """A reviewer may genuinely have nothing better. Refusing strands a real obligation;
        accepting silently launders a weak citation. So it stores, and reports the class."""
        resp = self.client.post(SOURCE_URL, json={"source_url": BLOG})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["researched_source_class"], "unofficial")

    # ── the approval gate ───────────────────────────────────────────────────

    def test_an_unsourced_candidate_cannot_be_approved(self):
        """Without this the queue lies: the candidate reads `approved` and is silently
        dropped at import with a reason nobody goes back to read."""
        resp = self.client.post(REVIEW_URL, json={"status": "approved"})
        self.assertEqual(resp.status_code, 409, resp.text)
        self.assertIn("no source", resp.json()["detail"])

    def test_the_same_candidate_approves_once_it_has_a_researched_source(self):
        self._install([
            {"status": "pending_review", "source": None, "researched_source_url": OFFICIAL}
        ])
        resp = self.client.post(REVIEW_URL, json={"status": "approved"})
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_a_model_sourced_candidate_still_approves(self):
        self._install([
            {"status": "pending_review", "source": OFFICIAL, "researched_source_url": None}
        ])
        self.assertEqual(self.client.post(REVIEW_URL, json={"status": "approved"}).status_code, 200)

    def test_rejecting_an_unsourced_candidate_is_always_allowed(self):
        """Refusing a bad candidate needs no citation — gating rejection would trap junk in
        the queue forever."""
        resp = self.client.post(REVIEW_URL, json={"status": "rejected"})
        self.assertEqual(resp.status_code, 200, resp.text)

    # ── the worklist number ─────────────────────────────────────────────────

    def test_needs_research_counts_only_what_nobody_has_sourced_yet(self):
        self._install([
            {"source_missing": True, "researched_source_url": None, "status": "pending_review"},
            {"source_missing": True, "researched_source_url": OFFICIAL, "status": "pending_review"},
            {"source_missing": False, "researched_source_url": None, "status": "pending_review"},
        ])
        counts = self.client.get("/api/admin/candidate-beam/runs/abc/items").json()["counts"]
        # source_missing stays frozen at what the BEAM produced; needs_research is the
        # actionable remainder and is the number that shrinks as research lands.
        self.assertEqual(counts["source_missing"], 2)
        self.assertEqual(counts["needs_research"], 1)
        self.assertEqual(counts["researched"], 1)


if __name__ == "__main__":
    unittest.main()
