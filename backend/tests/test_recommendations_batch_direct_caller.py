"""AIQ-1856 follow-up — the batch handler must survive a DIRECT (non-FastAPI) call.

Production regression, 2026-08-17 21:25 UTC, introduced by the AIQ-1856 slate-backgrounding
change and caught the next day in the Render log:

    ERROR:backend.main:request_id=f15c7240-... method=POST path=/api/test-drive/provision-staged
    TypeError: post_recommendations_batch() missing 1 required positional argument: 'background_tasks'

`backend/app/routers/test_drive.py:606` imports the handler and calls it as a plain Python
function (`_post_batch(request=stub, user=..., body=...)`) to build a staged services-state
blob. FastAPI injects `background_tasks` for an HTTP request; a direct call gets nothing, so
making the parameter required turned every `/api/test-drive/provision-staged` into a 500.

The original AIQ-1856 test suite missed this precisely because it passed `background_tasks`
explicitly — it exercised the signature it had just written, not the one the caller uses.

These tests pin BOTH callers: omitted (direct) and supplied (FastAPI).
"""
from __future__ import annotations

import os
import sys
import types
import unittest
from typing import Any, Dict, List
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ["RELOPASS_DISABLE_RATE_LIMITS"] = "1"
os.environ["RELOPASS_QUERY_COUNTER_OFF"] = "1"

from fastapi import BackgroundTasks  # noqa: E402

import backend.main as main  # noqa: E402
from backend.app.recommendations import router as rec_router  # noqa: E402
from backend.app.recommendations.types import RecommendationResponse  # noqa: E402

_EMP = {"id": "emp-1", "role": "EMPLOYEE"}
_ASG = {"id": "asg-1", "case_id": "case-1", "employee_user_id": "emp-1",
        "hr_user_id": "hr-1", "company_id": "co-1"}


class _DummySession:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


class BatchHandlerDirectCallTests(unittest.TestCase):
    def setUp(self):
        self.slate_calls: List[Any] = []

        def _fake_recommend(backend_key, criteria, top_n=10, company_id=None):
            return RecommendationResponse(
                category=backend_key, generated_at="2026-08-18T00:00:00+00:00",
                criteria_echo=dict(criteria), recommendations=[],
            )

        patches = [
            mock.patch.object(rec_router, "require_assignment_visibility", lambda _i, _u: dict(_ASG)),
            mock.patch.object(rec_router, "build_criteria_for_assignment",
                              return_value={"movers": {"destination_city": "Paris"}}),
            mock.patch.object(rec_router, "recommend", side_effect=_fake_recommend),
            mock.patch.object(rec_router, "_log_slate",
                              lambda *a, **k: self.slate_calls.append((a, k))),
            mock.patch.object(main.db, "list_case_services", return_value=[]),
            mock.patch.object(main.db, "list_case_service_answers", return_value=[]),
            mock.patch("backend.app.db.SessionLocal", lambda: _DummySession()),
            mock.patch("backend.app.crud.get_case", return_value=None),
            mock.patch("backend.policy_engine.PolicyEngine", side_effect=RuntimeError("no policy")),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        self.request = types.SimpleNamespace(
            state=types.SimpleNamespace(request_id="req-direct")
        )
        self.body: Dict[str, Any] = {
            "case_id": "case-1", "selected_services": ["movers", "schools"],
        }

    def test_direct_call_without_background_tasks_does_not_raise(self):
        """The exact call shape test_drive.py:606 uses. Pre-fix: TypeError."""
        result = rec_router.post_recommendations_batch(
            request=self.request, user=dict(_EMP), body=dict(self.body),
        )
        self.assertIn("results", result)
        self.assertIn("movers", result["results"])

    def test_direct_call_still_writes_the_slate_telemetry(self):
        """Backgrounding must not silently drop the writes for a caller that has no
        queue to drain — that would trade a 500 for silent data loss."""
        rec_router.post_recommendations_batch(
            request=self.request, user=dict(_EMP), body=dict(self.body),
        )
        self.assertEqual(len(self.slate_calls), 1,
                         "direct caller lost its slate write")

    def test_fastapi_style_call_still_defers_the_slate_write(self):
        """The AIQ-1856 property must survive: when a real queue is supplied, the writes
        are SCHEDULED, not run inline."""
        bg = BackgroundTasks()
        rec_router.post_recommendations_batch(
            request=self.request, background_tasks=bg,
            user=dict(_EMP), body=dict(self.body),
        )
        self.assertEqual(self.slate_calls, [], "slate ran inline on the request path")
        self.assertEqual(len(bg.tasks), 1, "slate write was not scheduled")

    def test_the_real_caller_signature_is_still_satisfiable(self):
        """Guard the coupling itself: bind test_drive's literal kwargs against the
        handler's signature, so renaming or re-requiring a parameter fails here."""
        import inspect
        sig = inspect.signature(rec_router.post_recommendations_batch)
        sig.bind(request=self.request, user=dict(_EMP), body=dict(self.body))


if __name__ == "__main__":
    unittest.main()
