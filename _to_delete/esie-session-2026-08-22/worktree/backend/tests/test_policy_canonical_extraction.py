"""
N11 / AIQ-851 — per-field confidence on the OpenAI canonical extraction path.

The canonical extractor emits one ``PolicyFactLLMRecord`` per fact, and each
record carries its own ``confidence_score`` — so this IS per-field confidence
(every fact is a field). N11 calibrates that score to a coarse 3-tier scale
(1.0 stated / 0.5 inferred / 0.1 absent) via the system prompt.

These tests lock in:
  * the model accepts a per-fact ``confidence_score`` and round-trips it, and
  * the OpenAI extractor's system prompt actually states the 3-tier scale, and
  * the per-fact confidence survives extraction (clearly-stated >= 0.8,
    silent/guessed <= 0.2) — the OpenAI sibling of the Anthropic-path tests in
    ``test_llm_policy_extractor.py``.

No live OPENAI_API_KEY is needed: the extractor takes an injected client, so we
mock the chat-completions response with the two boundary cases the 3-tier scale
defines.

Mirrors the query_counter pre-emption pattern from test_llm_policy_extractor.py.
"""
from __future__ import annotations

import json
import sys
import unittest
from unittest.mock import MagicMock

_qc_mod = MagicMock()
_qc_mod.install_query_counter = lambda *a, **kw: None
sys.modules.setdefault("backend.app.services.query_counter", _qc_mod)

from backend.app.schemas import (  # noqa: E402
    PolicyFactExtractionLLMInput,
    PolicyFactLLMRecord,
)
from backend.app.services.policy_canonical_extraction import (  # noqa: E402
    OpenAIPolicyCanonicalExtractor,
)


def _fake_openai_client_returning(facts):
    """Build a fake OpenAI client whose chat.completions returns `facts`."""
    message = MagicMock()
    message.content = json.dumps({"facts": facts})
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    client = MagicMock()
    client.chat.completions.create.return_value = response
    return client


SAMPLE_INPUT = PolicyFactExtractionLLMInput(
    chunk_id="chunk-1",
    text_content="Temporary housing capped at USD 6000 for 60 days.",
)


class TestRecordAcceptsConfidence(unittest.TestCase):
    """PolicyFactLLMRecord carries a per-fact confidence_score."""

    def test_model_round_trips_confidence_score(self):
        record = PolicyFactLLMRecord.model_validate(
            {"value_type": "monetary", "confidence_score": 0.95}
        )
        self.assertEqual(record.confidence_score, 0.95)
        self.assertEqual(record.model_dump(mode="json")["confidence_score"], 0.95)


class TestThreeTierPromptInstruction(unittest.TestCase):
    """The OpenAI extractor's system prompt states the 3-tier scale."""

    def test_system_prompt_states_three_tier_scale(self):
        captured = {}

        def _capture(*args, **kwargs):
            captured["messages"] = kwargs.get("messages")
            return _fake_openai_client_returning([]).chat.completions.create()

        client = MagicMock()
        client.chat.completions.create.side_effect = _capture
        extractor = OpenAIPolicyCanonicalExtractor(client=client, model="gpt-4.1-mini")
        extractor.extract(SAMPLE_INPUT)

        system_msg = next(
            m["content"] for m in captured["messages"] if m["role"] == "system"
        )
        for tier in ("1.0", "0.5", "0.1"):
            self.assertIn(tier, system_msg)


class TestPerFieldConfidenceCarriesThrough(unittest.TestCase):
    """Per-fact confidence survives extraction (N11 criteria 1 & 2, OpenAI path)."""

    def test_clearly_stated_fact_keeps_high_confidence(self):
        client = _fake_openai_client_returning(
            [
                {
                    "value_type": "monetary",
                    "source_quote": "Temporary housing capped at USD 6000",
                    "confidence_score": 1.0,
                }
            ]
        )
        extractor = OpenAIPolicyCanonicalExtractor(client=client, model="gpt-4.1-mini")
        out = extractor.extract(SAMPLE_INPUT)
        self.assertEqual(len(out.facts), 1)
        self.assertGreaterEqual(out.facts[0].confidence_score, 0.8)

    def test_absent_fact_keeps_low_confidence(self):
        client = _fake_openai_client_returning(
            [{"value_type": "text", "source_quote": None, "confidence_score": 0.1}]
        )
        extractor = OpenAIPolicyCanonicalExtractor(client=client, model="gpt-4.1-mini")
        out = extractor.extract(SAMPLE_INPUT)
        self.assertEqual(len(out.facts), 1)
        self.assertLessEqual(out.facts[0].confidence_score, 0.2)


if __name__ == "__main__":
    unittest.main()
