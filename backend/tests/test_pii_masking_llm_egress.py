"""SEC-03 / AIQ-1166 — PII masking at the LLM egress boundary (GDPR Art. 28/44).

Asserts that known-PII free text is redacted BEFORE it is handed to an LLM/
embeddings client. Each test mocks the client and inspects the payload the
client actually received, proving the raw PII never crosses the API boundary.

Sync tests only (no pytest-asyncio in CI). No network, no API keys.
"""
from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# A free-text query carrying several distinct PII shapes.
_PII_QUERY = (
    "My name is reachable at john.doe@acme.com or +33 6 12 34 56 78, "
    "IBAN FR7630006000011234567890189, passport 123456789."
)
_RAW_PII_TOKENS = [
    "john.doe@acme.com",
    "FR7630006000011234567890189",
    "123456789",
]


class AnthropicClientMaskingTests(unittest.TestCase):
    """The canonical chokepoint: AnthropicClient.complete() masks user_message
    before calling the Anthropic SDK. Every caller routed through this client
    (immigration answers, policy assistant RAG, roadmap generator) inherits it.
    """

    def _build_client_with_fake_sdk(self):
        from backend.app.services.policy_assistant_llm_client import AnthropicClient

        captured: dict = {}

        class _FakeBlock:
            type = "text"
            text = "ok"

        class _FakeResp:
            content = [_FakeBlock()]
            model = "claude-sonnet-4-6"
            stop_reason = "end_turn"

            class usage:  # noqa: N801 - mimic SDK attr access
                input_tokens = 1
                output_tokens = 1

        class _FakeMessages:
            def create(self, **kwargs):
                captured["kwargs"] = kwargs
                return _FakeResp()

        class _FakeSdkClient:
            messages = _FakeMessages()

        # Bypass __init__ (which needs ANTHROPIC_API_KEY + the anthropic pkg).
        client = AnthropicClient.__new__(AnthropicClient)
        client._client = _FakeSdkClient()
        return client, captured

    def test_user_message_is_masked_before_egress(self):
        from backend.app.services.policy_assistant_llm_client import LlmRequest

        client, captured = self._build_client_with_fake_sdk()
        client.complete(LlmRequest(system="STATIC", user_message=_PII_QUERY))

        sent = captured["kwargs"]["messages"][0]["content"]
        self.assertIn("[REDACTED_EMAIL]", sent)
        self.assertIn("[REDACTED_PHONE]", sent)
        self.assertIn("[REDACTED_IBAN]", sent)
        for raw in _RAW_PII_TOKENS:
            self.assertNotIn(raw, sent)


class PolicyRetrievalEmbeddingMaskingTests(unittest.TestCase):
    """policy_chunk_retriever.retrieve() masks the query before it is sent to the
    OpenAI embeddings endpoint — the chat-path masking does not cover embeddings.
    """

    def test_query_is_masked_before_embedding(self):
        from backend.app.services import policy_chunk_retriever

        captured: dict = {}

        class _Stop(Exception):
            pass

        class _RecordingEmbedder:
            def embed(self, text):
                captured["text"] = text
                raise _Stop()  # short-circuit before the DB query

            def embed_batch(self, texts):  # pragma: no cover - unused here
                return [[0.0] for _ in texts]

        with self.assertRaises(_Stop):
            policy_chunk_retriever.retrieve(
                company_id="c1", query=_PII_QUERY, embedder=_RecordingEmbedder()
            )

        sent = captured["text"]
        self.assertIn("[REDACTED_EMAIL]", sent)
        self.assertIn("[REDACTED_PHONE]", sent)
        self.assertIn("[REDACTED_IBAN]", sent)
        for raw in _RAW_PII_TOKENS:
            self.assertNotIn(raw, sent)


class PolicyQueryRedactorCoverageTests(unittest.TestCase):
    """redact_pii_from_query() now delegates to the canonical mask_pii(), so it
    covers IBAN / passport / SSN — categories the old bespoke regex missed.
    """

    def test_covers_iban_passport_ssn(self):
        from backend.app.services.policy_query_answering import redact_pii_from_query

        out = redact_pii_from_query(_PII_QUERY)
        self.assertIn("[REDACTED_IBAN]", out)
        for raw in _RAW_PII_TOKENS:
            self.assertNotIn(raw, out)


class BriefingPromptMaskingTests(unittest.TestCase):
    """briefing.build_user_prompt() anonymises the employee name and masks the
    free-text dependants field, while preserving structured personalisation.
    """

    def test_name_anonymised_and_dependants_masked(self):
        from backend.app.services.briefing import build_user_prompt

        prompt = build_user_prompt(
            "PUBLISHED CORPORATE POLICY TEXT",
            {
                "name": "Jane Smith",
                "grade": "L5",
                "destination": "Norway",
                "departure_date": "2026-07-01",
                "dependants": "spouse, reachable at jane.smith@acme.com",
            },
        )
        # Name never crosses the boundary.
        self.assertIn("[REDACTED_PERSON]", prompt)
        self.assertNotIn("Jane Smith", prompt)
        # PII typed into the dependants free-text is masked.
        self.assertIn("[REDACTED_EMAIL]", prompt)
        self.assertNotIn("jane.smith@acme.com", prompt)
        # Structured, non-PII personalisation is preserved (and the ISO date is
        # NOT false-masked into a phone number).
        self.assertIn("Norway", prompt)
        self.assertIn("L5", prompt)
        self.assertIn("2026-07-01", prompt)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
