"""
AIQ-833 / F2 — contract test for POST /api/policy-assistant/rag-query.

Proves the endpoint the frontend now calls returns exactly the flat shape the
frontend adapter (policyAssistantRagAdapter.ts) consumes:
  { answer_text, answer_kind, cited_chunks, model, cost_usd, audit_id, ... }
Company scoping is server-derived from the profile, never the request body.
The RAG engine itself is mocked — this isolates the HTTP contract + wiring.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import unittest
from typing import Any, Dict
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app, require_hr_or_employee

_HR_USER: Dict[str, Any] = {"id": "user-hr-a", "role": "hr", "email": "hr@company-a.test"}

_RAG_RESULT: Dict[str, Any] = {
    "answer_text": "Your housing allowance is 2000 EUR/month [chunk:c1].",
    "answer_kind": "answer",
    "cited_chunks": [
        {
            "id": "c1",
            "source_type": "matrix_benefit",
            "source_ref": "policy_config_benefits.b1",
            "chunk_text": "Housing cap is 2000 EUR/mo.",
        }
    ],
    "model": "claude",
    "usage": {"input_tokens": 10, "output_tokens": 5},
    "cost_usd": 0.0001,
    "latency_ms": 42,
    "audit_id": "audit-123",
    "trace_session_id": "trace-uuid-1234",
    "prompt_version_id": None,
    "canary_arm": None,
}

_RAG_ENGINE = "backend.app.services.policy_assistant_rag_engine.answer_policy_question"


class TestRagQueryEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[require_hr_or_employee] = lambda: _HR_USER
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_returns_flat_rag_shape_unchanged(self) -> None:
        """The endpoint passes the RAG engine's dict straight back — the exact
        shape the frontend adapter maps into PolicyAssistantAnswer."""
        with patch("backend.main.db.get_profile_record", return_value={"company_id": "co-a"}), \
                patch(_RAG_ENGINE, return_value=_RAG_RESULT) as mock_engine:
            resp = self.client.post(
                "/api/policy-assistant/rag-query", json={"question": "What is my housing allowance?"}
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # Fields the adapter reads:
        self.assertEqual(body["answer_kind"], "answer")
        self.assertEqual(body["answer_text"], _RAG_RESULT["answer_text"])
        self.assertEqual(body["cited_chunks"], _RAG_RESULT["cited_chunks"])
        self.assertEqual(body["audit_id"], "audit-123")
        # company_id is server-derived from the profile, NOT the body.
        _, kwargs = mock_engine.call_args
        self.assertEqual(kwargs["company_id"], "co-a")
        self.assertEqual(kwargs["question"], "What is my housing allowance?")

    def test_company_id_cannot_be_injected_from_body(self) -> None:
        """A company_id in the request body is ignored — scoping comes from the
        authenticated user's profile."""
        with patch("backend.main.db.get_profile_record", return_value={"company_id": "co-a"}), \
                patch(_RAG_ENGINE, return_value=_RAG_RESULT) as mock_engine:
            self.client.post(
                "/api/policy-assistant/rag-query",
                json={"question": "x", "company_id": "co-EVIL"},
            )
        _, kwargs = mock_engine.call_args
        self.assertEqual(kwargs["company_id"], "co-a")

    def test_trace_session_id_present_in_response(self) -> None:
        """Engine's trace_session_id is surfaced in the response so the frontend
        helpfulness control (POST /api/policy-assistant/helpfulness) can reference it."""
        with patch("backend.main.db.get_profile_record", return_value={"company_id": "co-a"}), \
                patch(_RAG_ENGINE, return_value=_RAG_RESULT):
            resp = self.client.post(
                "/api/policy-assistant/rag-query", json={"question": "Housing?"}
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("trace_session_id", body)
        self.assertEqual(body["trace_session_id"], "trace-uuid-1234")

    def test_missing_question_is_400(self) -> None:
        with patch("backend.main.db.get_profile_record", return_value={"company_id": "co-a"}):
            resp = self.client.post("/api/policy-assistant/rag-query", json={"question": "   "})
        self.assertEqual(resp.status_code, 400)

    def test_user_without_company_is_400(self) -> None:
        with patch("backend.main.db.get_profile_record", return_value={}):
            resp = self.client.post("/api/policy-assistant/rag-query", json={"question": "x"})
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
