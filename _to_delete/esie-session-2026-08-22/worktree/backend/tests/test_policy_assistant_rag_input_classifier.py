"""
AIQ-853 / F2-fu — the input out-of-scope classifier runs on the RAG endpoint.

After F2 (AIQ-833) cut the frontend to POST /api/policy-assistant/rag-query, the
deterministic input classifier stopped running for policy-assistant queries.
This restores it: out-of-scope / forbidden asks (legal advice, etc.) are refused
on a FAST PATH — before any retrieval or LLM call — in the same flat shape the
RAG engine returns, so the frontend adapter renders it unchanged.

These tests prove:
  1. an out-of-scope question short-circuits to a refusal WITHOUT invoking
     answer_policy_question (no LLM/retrieval),
  2. an in-policy question still flows through to answer_policy_question.
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

_EMP_USER: Dict[str, Any] = {"id": "user-emp-a", "role": "employee", "email": "emp@company-a.test"}
_RAG_ENGINE = "backend.app.services.policy_assistant_rag_engine.answer_policy_question"

_RAG_RESULT: Dict[str, Any] = {
    "answer_text": "Your shipment cap is 20 m3 [chunk:c1].",
    "answer_kind": "answer",
    "cited_chunks": [{"id": "c1", "source_type": "matrix_benefit", "source_ref": "b1", "chunk_text": "cap 20"}],
    "model": "claude",
    "cost_usd": 0.0001,
    "audit_id": "audit-1",
}


class TestRagInputClassifier(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[require_hr_or_employee] = lambda: _EMP_USER
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_out_of_scope_refuses_without_calling_engine(self) -> None:
        """A legal-advice question is refused by the input classifier on the fast
        path — answer_policy_question (LLM/retrieval) is never called."""
        with patch(_RAG_ENGINE) as mock_engine:
            resp = self.client.post(
                "/api/policy-assistant/rag-query",
                json={"question": "Can you give me legal advice about my visa lawsuit?"},
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn(body["answer_kind"], ("refusal_out_of_policy", "refusal_validation_failed"))
        self.assertEqual(body["cited_chunks"], [])
        self.assertTrue(body["answer_text"])  # a real refusal message, not blank
        mock_engine.assert_not_called()  # the whole point: no LLM on the fast path

    def test_in_policy_question_flows_to_engine(self) -> None:
        """An in-scope policy question is NOT short-circuited — it reaches the
        RAG engine and returns its grounded answer."""
        with patch("backend.main.db.get_profile_record", return_value={"company_id": "co-a"}), \
                patch(_RAG_ENGINE, return_value=_RAG_RESULT) as mock_engine:
            resp = self.client.post(
                "/api/policy-assistant/rag-query",
                json={"question": "What is my shipment cap under the relocation policy?"},
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["answer_kind"], "answer")
        mock_engine.assert_called_once()


if __name__ == "__main__":
    unittest.main()
