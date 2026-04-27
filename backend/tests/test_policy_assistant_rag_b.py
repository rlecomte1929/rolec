"""
Sprint B integration tests for the Policy Assistant RAG engine.

Covers prompt assembly, validator, retry-on-validation-failure, refusal
fallback, multi-turn memory, and citation extraction. All LLM calls
go through MockClient — no Anthropic API key required.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Force mock LLM + hash embedder so nothing in this suite ever calls
# an external API.
os.environ["POLICY_ASSISTANT_LLM"] = "mock"
os.environ["POLICY_ASSISTANT_EMBEDDER"] = "hash"

from backend.services import (  # noqa: E402
    policy_assistant_rag_engine as rag,
    policy_assistant_session_memory as session_memory,
    policy_chunk_retriever,
)
from backend.services.policy_assistant_llm_client import (  # noqa: E402
    LlmRequest,
    MockClient,
    estimate_cost_usd,
    extract_cited_chunk_ids,
    contains_forbidden_phrase,
)


# --- Validator unit tests --------------------------------------------------

class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            {"id": "abc", "chunk_text": "Housing"},
            {"id": "def", "chunk_text": "Shipment"},
        ]

    def test_passes_with_valid_citation(self):
        self.assertIsNone(rag._validate_answer(
            "Housing covers USD 4,500/month [chunk:abc].", self.chunks))

    def test_passes_canonical_refusal(self):
        self.assertIsNone(rag._validate_answer(rag.REFUSAL_TEXT, self.chunks))

    def test_rejects_no_citations(self):
        self.assertEqual(
            rag._validate_answer("Housing is covered.", self.chunks),
            "no_citations",
        )

    def test_rejects_fabricated_chunk_id(self):
        err = rag._validate_answer(
            "Housing covers USD 4,500/month [chunk:fake999].", self.chunks)
        self.assertTrue(err.startswith("fabricated_chunk_ids:"))
        self.assertIn("fake999", err)

    def test_rejects_empty_answer(self):
        self.assertEqual(rag._validate_answer("", self.chunks), "empty_answer")
        self.assertEqual(rag._validate_answer("   ", self.chunks), "empty_answer")

    def test_rejects_forbidden_phrase(self):
        err = rag._validate_answer(
            "As an AI, I covered housing [chunk:abc].", self.chunks)
        self.assertTrue(err.startswith("forbidden_phrase:"))


class CitationExtractionTests(unittest.TestCase):
    def test_extract_dedup_preserves_order(self):
        text = "First [chunk:abc], second [chunk:def], dup [chunk:abc]."
        self.assertEqual(extract_cited_chunk_ids(text), ["abc", "def"])

    def test_no_citations_returns_empty(self):
        self.assertEqual(extract_cited_chunk_ids("Plain text."), [])

    def test_handles_uuids_with_dashes(self):
        text = "[chunk:550e8400-e29b-41d4-a716-446655440000]"
        self.assertEqual(
            extract_cited_chunk_ids(text),
            ["550e8400-e29b-41d4-a716-446655440000"],
        )


class CostEstimateTests(unittest.TestCase):
    def test_sonnet_pricing(self):
        cost = estimate_cost_usd(
            {"input_tokens": 1000, "output_tokens": 200},
            "claude-sonnet-4-6",
        )
        # 1000 in × $3/M + 200 out × $15/M = $0.003 + $0.003 = $0.006
        self.assertAlmostEqual(cost, 0.006, places=4)

    def test_unknown_model_returns_zero(self):
        self.assertEqual(
            estimate_cost_usd({"input_tokens": 999, "output_tokens": 999},
                              "claude-fake-model"),
            0.0,
        )


# --- Engine end-to-end tests with mocked retriever -------------------------

class _StubAuditDb:
    """Minimal stub: rag_engine writes audits via db.insert_… helpers.
    We don't need persistence for these tests; just answer 'no audit
    table' so the audit-write path no-ops gracefully."""

    def policy_hardening_tables_available(self):
        return False


class RagEngineEndToEndTests(unittest.TestCase):
    def setUp(self):
        session_memory._reset_all_for_tests()
        # Stub the retriever — engine tests focus on prompt + validator
        # + retry, not on the chunk index itself (Sprint A covers that).
        self._retrieve_patcher = mock.patch.object(
            policy_chunk_retriever, "retrieve",
            return_value=[
                {"id": "ch-1", "source_type": "matrix_benefit",
                 "source_ref": "policy_config_benefits.b1",
                 "chunk_text": "Housing allowance: USD 4,500 per month."},
                {"id": "ch-2", "source_type": "matrix_benefit",
                 "source_ref": "policy_config_benefits.b2",
                 "chunk_text": "Household goods shipment: USD 12,000 one time."},
            ],
        )
        self._retrieve_patcher.start()
        self.addCleanup(self._retrieve_patcher.stop)

        # Replace the audit-writing db with a stub.
        self._db_patcher = mock.patch.object(rag, "db", _StubAuditDb())
        self._db_patcher.start()
        self.addCleanup(self._db_patcher.stop)

    def test_happy_path_grounded_answer(self):
        client = MockClient(responses_by_pattern={
            "housing": "Housing allowance is USD 4,500/month [chunk:ch-1].",
        })
        result = rag.answer_policy_question(
            company_id="co-a", user_id="u-1",
            question="What's the housing allowance?",
            client=client,
        )
        self.assertEqual(result["answer_kind"], "answer")
        self.assertIn("USD 4,500", result["answer_text"])
        self.assertEqual(len(result["cited_chunks"]), 1)
        self.assertEqual(result["cited_chunks"][0]["id"], "ch-1")
        self.assertGreater(result["cost_usd"], 0)
        self.assertGreaterEqual(result["latency_ms"], 0)

    def test_refusal_when_chunks_dont_cover_question(self):
        # MockClient defaults to the canonical refusal text when no
        # pattern matches.
        client = MockClient(responses_by_pattern={})
        result = rag.answer_policy_question(
            company_id="co-a", user_id="u-1",
            question="What's the weather in Tokyo?",
            client=client,
        )
        self.assertEqual(result["answer_kind"], "refusal_out_of_policy")
        self.assertEqual(result["answer_text"], rag.REFUSAL_TEXT)
        self.assertEqual(result["cited_chunks"], [])

    def test_validator_retry_then_succeeds(self):
        # First response: no citations (invalid). Second response: valid.
        # MockClient pattern matches BOTH calls because the user message
        # contains the same question. Use a stateful mock for asymmetric
        # responses across calls.
        responses_in_order = [
            "Housing is covered.",
            "Housing covers USD 4,500/month [chunk:ch-1].",
        ]
        call_count = {"n": 0}

        def stateful_complete(req: LlmRequest):
            i = call_count["n"]
            call_count["n"] += 1
            text = responses_in_order[min(i, len(responses_in_order) - 1)]
            return {
                "text": text, "model": req.model, "stop_reason": "end_turn",
                "usage": {"input_tokens": 100, "output_tokens": 50},
            }

        client = MockClient()
        client.complete = stateful_complete  # type: ignore[assignment]

        result = rag.answer_policy_question(
            company_id="co-a", user_id="u-1",
            question="What's the housing allowance?",
            client=client,
        )
        self.assertEqual(result["answer_kind"], "answer")
        self.assertIn("USD 4,500", result["answer_text"])
        self.assertEqual(call_count["n"], 2)  # retry happened

    def test_validator_retry_fails_falls_back_to_refusal(self):
        # Both attempts produce ungrounded answers → fall back to canonical refusal.
        client = MockClient(responses_by_pattern={
            "housing": "Housing is covered.",  # no citations on both calls
        })
        result = rag.answer_policy_question(
            company_id="co-a", user_id="u-1",
            question="What's the housing allowance?",
            client=client,
        )
        self.assertEqual(result["answer_kind"], "refusal_validation_failed")
        self.assertEqual(result["answer_text"], rag.REFUSAL_TEXT)

    def test_fabricated_chunk_id_rejected(self):
        client = MockClient(responses_by_pattern={
            "housing": "Housing covers USD 4,500/month [chunk:totally-fake-id].",
        })
        result = rag.answer_policy_question(
            company_id="co-a", user_id="u-1",
            question="What's the housing allowance?",
            client=client,
        )
        # First call produces a fabricated id → retry; mock returns same
        # text on retry → falls back to refusal.
        self.assertEqual(result["answer_kind"], "refusal_validation_failed")

    def test_session_memory_records_turn(self):
        client = MockClient(responses_by_pattern={
            "housing": "Housing covers USD 4,500/month [chunk:ch-1].",
        })
        rag.answer_policy_question(
            company_id="co-a", user_id="u-1",
            question="What's the housing allowance?",
            session_id="sess-A",
            client=client,
        )
        turns = session_memory.get_recent_turns("sess-A")
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0][0], "What's the housing allowance?")

    def test_session_memory_rolls_at_max_turns(self):
        # MAX_TURNS is 4 per design doc. Push 6 turns; expect last 4.
        client = MockClient(responses_by_pattern={
            "housing": "Housing covers USD 4,500/month [chunk:ch-1].",
        })
        for i in range(6):
            rag.answer_policy_question(
                company_id="co-a", user_id="u-1",
                question=f"housing question #{i}",
                session_id="sess-roll",
                client=client,
            )
        turns = session_memory.get_recent_turns("sess-roll")
        self.assertEqual(len(turns), 4)
        # Should be the LAST 4 (questions 2, 3, 4, 5).
        first_q = turns[0][0]
        self.assertEqual(first_q, "housing question #2")
        last_q = turns[-1][0]
        self.assertEqual(last_q, "housing question #5")

    def test_no_session_id_skips_memory(self):
        client = MockClient(responses_by_pattern={
            "housing": "Housing covers USD 4,500/month [chunk:ch-1].",
        })
        rag.answer_policy_question(
            company_id="co-a", user_id="u-1",
            question="anonymous one-off question",
            session_id=None,
            client=client,
        )
        # No session id → nothing stored.
        self.assertEqual(session_memory._session_count_for_tests(), 0)

    def test_question_required(self):
        client = MockClient()
        with self.assertRaises(ValueError):
            rag.answer_policy_question(
                company_id="co-a", user_id="u-1", question="", client=client)
        with self.assertRaises(ValueError):
            rag.answer_policy_question(
                company_id="co-a", user_id="u-1", question="   ", client=client)

    def test_company_id_required(self):
        client = MockClient()
        with self.assertRaises(ValueError):
            rag.answer_policy_question(
                company_id="", user_id="u-1", question="q", client=client)


class PromptAssemblyTests(unittest.TestCase):
    """Assert the user message contains the right sections — guards
    against accidentally dropping the company scoping or the chunks."""

    def test_user_message_contains_chunks_and_question(self):
        msg = rag._build_user_message(
            company_label="NovoLike",
            question="What about housing?",
            chunks=[{"id": "ch-1", "chunk_text": "Housing covers USD 4500/month."}],
            turns=[],
        )
        self.assertIn("COMPANY: NovoLike", msg)
        self.assertIn("What about housing?", msg)
        self.assertIn("[chunk:ch-1]", msg)

    def test_user_message_includes_employee_context_when_present(self):
        msg = rag._build_user_message(
            company_label="NovoLike",
            question="q",
            chunks=[],
            turns=[],
            employee_context={
                "assignment_type": "permanent",
                "employee_level": "director",
                "country": "SG",
            },
        )
        self.assertIn("assignment_type=permanent", msg)
        self.assertIn("employee_level=director", msg)
        self.assertIn("country=SG", msg)

    def test_user_message_includes_prior_turns(self):
        msg = rag._build_user_message(
            company_label="NovoLike",
            question="and the kids?",
            chunks=[],
            turns=[
                ("does the policy cover relocation?", "Yes [chunk:x]."),
                ("what about my partner?", "Yes [chunk:y]."),
            ],
        )
        self.assertIn("USER: does the policy cover relocation?", msg)
        self.assertIn("USER: what about my partner?", msg)


if __name__ == "__main__":
    unittest.main()
