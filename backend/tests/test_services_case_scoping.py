"""AIQ-1249b — case_id acceptance on the services endpoints.

The change let three endpoints accept a ``case_id`` gate in addition to the
legacy ``assignment_id`` gate:
  - GET  /api/services/context
  - GET  /api/services/questions
  - POST /api/recommendations/batch

Both gates resolve through the same assignment-visibility helper
(``_require_assignment_visibility`` in backend.main / ``require_assignment_visibility``
in backend.app.auth_deps), which rejects cross-case / unauthorized access. The
legacy ``assignment_id`` path must keep working unchanged.

App-mounted test (mounts the prod app `backend.main.app`). The auth dependency
is overridden directly (both the main.py and auth_deps copies of
``require_hr_or_employee``), and the shared mocked ``backend.database.db`` (the
root conftest installs it as a MagicMock) has just the four methods these
endpoints touch stubbed: ``get_assignment_by_id`` / ``get_assignment_by_case_id``
(the resolution surface) plus ``list_case_services`` / ``list_case_service_answers``.
No live DB is needed.
"""
from __future__ import annotations

import os
import sys
import unittest
from typing import Any, Dict, Optional
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ["RELOPASS_DISABLE_RATE_LIMITS"] = "1"
os.environ["RELOPASS_QUERY_COUNTER_OFF"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

import backend.main as main  # noqa: E402
import backend.app.auth_deps as auth_deps  # noqa: E402

# The employee who owns case-1 / asg-1. UserRole values are uppercase.
_EMP = {"id": "emp-1", "role": "EMPLOYEE"}

# Authorized assignment+case (employee = emp-1).
_ASG = {
    "id": "asg-1",
    "case_id": "case-1",
    "employee_user_id": "emp-1",
    "hr_user_id": "hr-1",
    "company_id": "co-1",
}
# A different tenant's assignment+case (employee = emp-2) — emp-1 must NOT reach it.
_OTHER = {
    "id": "asg-2",
    "case_id": "case-2",
    "employee_user_id": "emp-2",
    "hr_user_id": "hr-9",
    "company_id": "co-9",
}


def _by_id(aid: str) -> Optional[Dict[str, Any]]:
    return {"asg-1": _ASG, "asg-2": _OTHER}.get(aid)


def _by_case(cid: str) -> Optional[Dict[str, Any]]:
    return {"case-1": _ASG, "case-2": _OTHER}.get(cid)


class _DummySession:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


class ServicesCaseScopingTests(unittest.TestCase):
    def setUp(self):
        # Auth: both endpoint families resolve a different require_hr_or_employee
        # object (main.py's vs auth_deps'). Override both so the employee is
        # authenticated regardless of which copy the route depends on.
        main.app.dependency_overrides[main.require_hr_or_employee] = lambda: dict(_EMP)
        main.app.dependency_overrides[auth_deps.require_hr_or_employee] = lambda: dict(_EMP)
        self.addCleanup(main.app.dependency_overrides.clear)

        # Resolution surface (shared mocked db object — main.db is auth_deps.db).
        patches = [
            mock.patch.object(main.db, "get_assignment_by_id", side_effect=_by_id),
            mock.patch.object(main.db, "get_assignment_by_case_id", side_effect=_by_case),
            mock.patch.object(main.db, "list_case_services", return_value=[]),
            mock.patch.object(main.db, "list_case_service_answers", return_value=[]),
            # Avoid touching a live DB inside the case-context block.
            mock.patch.object(main.app_crud, "get_case", return_value=None),
            mock.patch.object(main, "SessionLocal", lambda: _DummySession()),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        self.client = TestClient(main.app, raise_server_exceptions=False)

    # 1. /api/services/context — case_id is at parity with assignment_id.
    def test_context_case_id_parity_with_assignment_id(self):
        by_case = self.client.get("/api/services/context?case_id=case-1")
        by_asg = self.client.get("/api/services/context?assignment_id=asg-1")
        self.assertEqual(by_case.status_code, 200, by_case.text)
        self.assertEqual(by_asg.status_code, 200, by_asg.text)
        self.assertEqual(by_case.json()["assignment_id"], "asg-1")
        self.assertEqual(by_case.json()["case_id"], "case-1")
        # Identical payload from either gate — proves case_id resolves to asg-1.
        self.assertEqual(by_case.json(), by_asg.json())

    # 2. /api/services/questions works with case_id.
    def test_questions_accepts_case_id(self):
        # fallback_services seeds a selected service so the question generator runs.
        resp = self.client.get(
            "/api/services/questions?case_id=case-1&fallback_services=housing"
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIn("questions", body)
        self.assertEqual(body["selected_services"], ["housing"])

    # 3. /api/recommendations/batch accepts case_id (body) and resolves the case.
    def test_batch_accepts_case_id(self):
        # No selected_services + empty list_case_services → the endpoint returns
        # its "nothing selected" envelope, which still proves the case_id gate
        # resolved (a bad case_id would 404/403 before this point).
        resp = self.client.post("/api/recommendations/batch", json={"case_id": "case-1"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIn("results", resp.json())

    # 4a. Cross-case rejection on /api/services/context.
    def test_context_cross_case_rejected(self):
        # case-2 belongs to emp-2; emp-1 must be refused.
        resp = self.client.get("/api/services/context?case_id=case-2")
        self.assertEqual(resp.status_code, 403, resp.text)

    # 4b. Cross-case rejection on /api/recommendations/batch.
    def test_batch_cross_case_rejected(self):
        resp = self.client.post("/api/recommendations/batch", json={"case_id": "case-2"})
        self.assertEqual(resp.status_code, 403, resp.text)

    # 4c. Unknown case_id → 404 (assignment not found), not a 500.
    def test_context_unknown_case_id_not_found(self):
        resp = self.client.get("/api/services/context?case_id=case-nope")
        self.assertEqual(resp.status_code, 404, resp.text)

    # 5. Back-compat: the legacy assignment_id path still works on batch.
    def test_batch_legacy_assignment_id_still_works(self):
        resp = self.client.post(
            "/api/recommendations/batch", json={"assignment_id": "asg-1"}
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIn("results", resp.json())

    # 5b. Neither gate → 400 (guards the new "case_id or assignment_id" branch).
    def test_context_requires_a_gate(self):
        resp = self.client.get("/api/services/context")
        self.assertEqual(resp.status_code, 400, resp.text)

    # 6. AIQ-1456: every selected category renders a block — a category whose
    #    recommend() run fails must still appear (as an empty block), not vanish.
    def test_batch_includes_every_selected_category_even_when_one_fails(self):
        from backend.app.recommendations import router as rec_router
        from backend.app.recommendations.types import RecommendationResponse

        criteria_map = {
            "living_areas": {"destination_city": "Oslo"},
            "movers": {"destination_city": "Oslo"},
        }

        def _fake_recommend(backend_key, criteria, top_n=10, company_id=None):
            if backend_key == "living_areas":
                raise RuntimeError("boom: housing plugin failed")
            return RecommendationResponse(
                category=backend_key,
                generated_at="2026-01-01T00:00:00Z",
                criteria_echo={},
                recommendations=[],
            )

        with mock.patch.object(rec_router, "build_criteria_for_assignment", return_value=criteria_map), \
                mock.patch.object(rec_router, "recommend", side_effect=_fake_recommend):
            resp = self.client.post(
                "/api/recommendations/batch",
                json={"case_id": "case-1", "selected_services": ["housing", "movers"]},
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        results = resp.json()["results"]
        # Both selected categories present — the failing housing run is NOT dropped.
        self.assertIn("living_areas", results)
        self.assertIn("movers", results)
        # The failed category is an explicit empty block, not missing.
        self.assertEqual(results["living_areas"]["recommendations"], [])
        self.assertEqual(results["living_areas"]["criteria_echo"].get("status"), "unavailable")

    # 7. AIQ-1550: a case with no destination city yet must STILL run movers — HR's
    #    company-scoped curation is the source of truth, so movers must surface HR's
    #    picks instead of being skipped into the "HR is finalizing" empty state.
    def test_batch_movers_runs_when_no_destination_but_company_present(self):
        from backend.app.recommendations import router as rec_router
        from backend.app.recommendations.types import RecommendationResponse

        called: list[str] = []

        def _fake_recommend(backend_key, criteria, top_n=10, company_id=None):
            called.append(backend_key)
            return RecommendationResponse(
                category=backend_key, generated_at="2026-01-01T00:00:00Z",
                criteria_echo={}, recommendations=[],
            )

        # Blank destination city; case-1 resolves to company co-1.
        criteria_map = {"movers": {"destination_city": ""}}
        with mock.patch.object(rec_router, "build_criteria_for_assignment", return_value=criteria_map), \
                mock.patch.object(rec_router, "recommend", side_effect=_fake_recommend):
            resp = self.client.post(
                "/api/recommendations/batch",
                json={"case_id": "case-1", "selected_services": ["movers"]},
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        # The fix: movers was NOT skipped on the blank destination — recommend() ran for it.
        self.assertIn("movers", called)
        self.assertIn("movers", resp.json()["results"])

    # 8. AIQ-1550: a legacy text-id HR account (no assignment.company_id, no profiles row) must
    #    still resolve its company via hr_users (get_hr_company_id) so HR curation applies.
    def test_batch_resolves_company_via_hr_users_for_legacy_hr(self):
        from backend.app.recommendations import router as rec_router
        from backend.app.recommendations.types import RecommendationResponse
        # The router resolves the company via a *dynamic* `from ...database import db` (inside the
        # handler), so the company-resolution methods must be patched on backend.database.db, which
        # can differ from main.db under full-suite import ordering (single-file runs coincidentally
        # share the object).
        import backend.database as _bdb

        # Assignment with a legacy hr id and NO company_id key (as case_assignments has none).
        legacy_asg = {
            "id": "asg-1", "case_id": "case-1",
            "employee_user_id": "emp-1", "hr_user_id": "hr-legacy-textid",
        }
        seen_company: list = []

        def _fake_recommend(backend_key, criteria, top_n=10, company_id=None):
            seen_company.append(company_id)
            return RecommendationResponse(
                category=backend_key, generated_at="2026-01-01T00:00:00Z",
                criteria_echo={}, recommendations=[],
            )

        with mock.patch.object(main.db, "get_assignment_by_case_id", side_effect=lambda cid: legacy_asg if cid == "case-1" else None), \
                mock.patch.object(main.db, "get_assignment_by_id", side_effect=lambda aid: legacy_asg if aid == "asg-1" else None), \
                mock.patch.object(_bdb.db, "get_hr_company_id", return_value="co-from-hr-users") as ghc, \
                mock.patch.object(_bdb.db, "get_profile_record", return_value=None), \
                mock.patch.object(rec_router, "build_criteria_for_assignment", return_value={"movers": {"destination_city": "Oslo"}}), \
                mock.patch.object(rec_router, "recommend", side_effect=_fake_recommend):
            resp = self.client.post(
                "/api/recommendations/batch",
                json={"case_id": "case-1", "selected_services": ["movers"]},
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        # hr_users was consulted with the legacy id, and its company flowed into recommend()
        # (so apply_hr_curation can run for this tenant instead of being skipped).
        ghc.assert_called_with("hr-legacy-textid")
        self.assertIn("co-from-hr-users", seen_company)


if __name__ == "__main__":
    unittest.main()
