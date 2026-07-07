"""AIQ-1438 / AIQ-1439 — new admin workflow analytics endpoints.

Pins the contract of:
  GET /api/admin/workflow/funnel          — stage-to-stage conversion
  GET /api/admin/workflow/assistant-topics — assistant questions ranked by canonical topic

Funnel math and topic ranking are tested against known data (db helpers patched).
A third test hits both endpoints against the real (SQLite) db to prove the
dialect-aware SQL runs without error — guarding the PG/SQLite JSON split.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.app.auth_deps import require_admin  # noqa: E402

_ROUTER = "backend.app.routers.admin_workflow_analytics"


class TestWorkflowFunnel(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[require_admin] = lambda: {"is_admin": True, "id": "admin-1"}
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.pop(require_admin, None)

    def test_funnel_conversion_math(self):
        counts = {
            "case_created": 100,
            "services_selected": 80,
            "recommendations_generated": 60,
            "supplier_selected": 30,
            "rfq_created": 15,
            "quote_accepted": 6,
        }
        with patch(f"{_ROUTER}.db") as mock_db:
            mock_db.count_analytics_events_by_name.return_value = counts
            resp = self.client.get("/api/admin/workflow/funnel?days=30")
        self.assertEqual(resp.status_code, 200, resp.text)
        stages = resp.json()["stages"]
        self.assertEqual(len(stages), 6)
        # First stage: no prev conversion, 100% from start.
        self.assertEqual(stages[0]["stage"], "case_created")
        self.assertIsNone(stages[0]["conversion_from_prev_pct"])
        self.assertEqual(stages[0]["conversion_from_start_pct"], 100.0)
        # services_selected: 80/100 from prev and from start.
        self.assertEqual(stages[1]["conversion_from_prev_pct"], 80.0)
        self.assertEqual(stages[1]["conversion_from_start_pct"], 80.0)
        # supplier_selected: 30/60 = 50% from prev, 30/100 = 30% from start.
        self.assertEqual(stages[3]["conversion_from_prev_pct"], 50.0)
        self.assertEqual(stages[3]["conversion_from_start_pct"], 30.0)

    def test_funnel_zero_start_no_division_error(self):
        with patch(f"{_ROUTER}.db") as mock_db:
            mock_db.count_analytics_events_by_name.return_value = {}
            resp = self.client.get("/api/admin/workflow/funnel")
        self.assertEqual(resp.status_code, 200, resp.text)
        for s in resp.json()["stages"]:
            self.assertEqual(s["count"], 0)
            self.assertEqual(s["conversion_from_start_pct"], 0.0)


class TestAssistantTopics(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[require_admin] = lambda: {"is_admin": True, "id": "admin-1"}
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.pop(require_admin, None)

    def test_topics_ranked_and_rates(self):
        rows = [
            {"topic": "housing", "event_name": "assistant_question_asked", "cnt": 10},
            {"topic": "housing", "event_name": "assistant_question_supported", "cnt": 7},
            {"topic": "housing", "event_name": "assistant_question_unsupported", "cnt": 3},
            {"topic": "immigration", "event_name": "assistant_question_asked", "cnt": 4},
            {"topic": "immigration", "event_name": "assistant_refusal_shown", "cnt": 1},
        ]
        with patch(f"{_ROUTER}.db") as mock_db:
            mock_db.count_assistant_events_by_topic.return_value = rows
            mock_db.count_analytics_events_by_name.return_value = {
                "assistant_question_asked": 14,
                "assistant_question_supported": 7,
                "assistant_question_unsupported": 3,
                "assistant_refusal_shown": 1,
            }
            resp = self.client.get("/api/admin/workflow/assistant-topics?days=7")
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        topics = data["topics"]
        # Ranked by asked desc → housing (10) before immigration (4).
        self.assertEqual(topics[0]["topic"], "housing")
        self.assertEqual(topics[0]["asked"], 10)
        self.assertEqual(topics[0]["support_rate_pct"], 70.0)  # 7/(7+3)
        self.assertEqual(topics[1]["topic"], "immigration")
        self.assertEqual(topics[1]["refusal_rate_pct"], 25.0)  # 1/4
        # Overall block present.
        self.assertEqual(data["overall"]["support_rate_pct"], 70.0)

    def test_topics_none_topic_bucketed(self):
        rows = [{"topic": None, "event_name": "assistant_question_asked", "cnt": 2}]
        with patch(f"{_ROUTER}.db") as mock_db:
            mock_db.count_assistant_events_by_topic.return_value = rows
            mock_db.count_analytics_events_by_name.return_value = {}
            resp = self.client.get("/api/admin/workflow/assistant-topics")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["topics"][0]["topic"], "(uncategorised)")


class TestRealDbNoSqlCrash(unittest.TestCase):
    """Hit both endpoints against the real (SQLite) db — proves the dialect-aware
    JSON GROUP BY and the funnel query execute without error (empty data is fine)."""

    def setUp(self):
        app.dependency_overrides[require_admin] = lambda: {"is_admin": True, "id": "admin-1"}
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.pop(require_admin, None)

    def test_funnel_real_db_200(self):
        resp = self.client.get("/api/admin/workflow/funnel")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(len(resp.json()["stages"]), 6)

    def test_assistant_topics_real_db_200(self):
        resp = self.client.get("/api/admin/workflow/assistant-topics")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIn("topics", resp.json())
        self.assertIn("overall", resp.json())


if __name__ == "__main__":
    unittest.main()
