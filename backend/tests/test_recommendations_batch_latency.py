"""AIQ-1856 — POST /api/recommendations/batch must not make the caller wait on telemetry.

Production incident (BUG-260817-8F10): request_id=2d9ad2fe-613d-4064-9308-d96e8476b8aa
returned **200 OK** after **11,963 ms**. The browser client aborts at 12,000 ms, so it
hung up 77 ms before the response landed and reported it as a status-0 network failure —
the employee saw "cannot reach server" for work the server had already finished.

The Render log shows where the time went:

    20:37:38.354  recommendations_batch succeeded dur_ms=4456.23   <- answer ready
    20:37:44.918  analytics event=recommendations_generated        <- 6.5s later
    20:37:45.056  status=200 elapsed_ms=11963

Those 6.5 seconds are the ``_log_slate`` loop, which re-runs the whole engine a second
time per category (``recommend_debug``) purely to persist learned-ranking training rows —
after the answer the caller is waiting for has been computed. Nothing in the response
depends on it, and it already swallows every exception.

This test pins the ordering: the slate writes are *scheduled*, not *awaited*. It calls
the route function directly (rather than through TestClient, which drains background
tasks before returning) so "was it called before we returned?" is observable.
"""
from __future__ import annotations

import os
import sys
import types
import unittest
from typing import Any, Dict
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
_ASG = {
    "id": "asg-1",
    "case_id": "case-1",
    "employee_user_id": "emp-1",
    "hr_user_id": "hr-1",
    "company_id": "co-1",
}


class _DummySession:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


class BatchSlateLoggingIsBackgroundedTests(unittest.TestCase):
    def setUp(self):
        self.slate_calls: list = []

        def _record_slate(*args, **kwargs):
            self.slate_calls.append((args, kwargs))

        self._record_slate = _record_slate

        def _fake_recommend(backend_key, criteria, top_n=10, company_id=None):
            return RecommendationResponse(
                category=backend_key,
                generated_at="2026-08-17T20:37:38+00:00",
                criteria_echo=dict(criteria),
                recommendations=[],
            )

        patches = [
            mock.patch.object(rec_router, "require_assignment_visibility", lambda _id, _u: dict(_ASG)),
            mock.patch.object(rec_router, "build_criteria_for_assignment",
                              return_value={"movers": {"destination_city": "Paris"},
                                            "schools": {"destination_city": "Paris"}}),
            mock.patch.object(rec_router, "recommend", side_effect=_fake_recommend),
            mock.patch.object(rec_router, "_log_slate", _record_slate),
            mock.patch.object(main.db, "list_case_services", return_value=[]),
            mock.patch.object(main.db, "list_case_service_answers", return_value=[]),
            mock.patch("backend.app.db.SessionLocal", lambda: _DummySession()),
            mock.patch("backend.app.crud.get_case", return_value=None),
            mock.patch("backend.policy_engine.PolicyEngine", side_effect=RuntimeError("no policy in test")),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _call(self, background_tasks: BackgroundTasks) -> Dict[str, Any]:
        request = types.SimpleNamespace(state=types.SimpleNamespace(request_id="req-1856"))
        return rec_router.post_recommendations_batch(
            request=request,
            background_tasks=background_tasks,
            user=dict(_EMP),
            body={"assignment_id": "asg-1", "selected_services": ["movers", "schools"]},
        )

    def test_slate_logging_does_not_run_before_the_response_is_returned(self):
        """The 6.5s of re-run-the-engine telemetry must be off the critical path.

        Against the pre-fix code this fails: ``_log_slate`` is called inline, so
        ``slate_calls`` is already populated by the time the handler returns.
        """
        bg = BackgroundTasks()
        result = self._call(bg)

        self.assertEqual(
            self.slate_calls,
            [],
            "slate telemetry ran inline — the caller is still paying for it",
        )
        self.assertIn("results", result)
        self.assertEqual(sorted(result["results"]), ["movers", "schools"])

    def test_slate_logging_is_scheduled_once_per_category(self):
        """Backgrounded, not dropped — the training data must still be written."""
        bg = BackgroundTasks()
        result = self._call(bg)

        slate_tasks = [t for t in bg.tasks if t.func is self._record_slate]
        self.assertEqual(
            len(slate_tasks),
            len(result["results"]),
            "expected one scheduled slate write per returned category",
        )
        scheduled_categories = sorted(t.args[0] for t in slate_tasks)
        self.assertEqual(scheduled_categories, ["movers", "schools"])
        for task in slate_tasks:
            self.assertEqual(task.kwargs["case_id"], "case-1")
            self.assertEqual(task.kwargs["assignment_id"], "asg-1")
            self.assertEqual(task.kwargs["request_id"], "req-1856")

        # And they really do write when the background pass runs.
        for task in slate_tasks:
            task.func(*task.args, **task.kwargs)
        self.assertEqual(len(self.slate_calls), 2)


if __name__ == "__main__":
    unittest.main()
