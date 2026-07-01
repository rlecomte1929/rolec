"""
Relocation-assistant Slice 3 — inject anonymised applicant context into the
grounded answer so the engine can tailor WHICH requirements matter, WITHOUT
weakening grounding: the context is a hint, never a citable source, and the N5
grounding verifier still runs. The refusal path must never reach the LLM.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.immigration_answer_engine import generate_immigration_answer
from backend.app.services.policy_assistant_llm_client import MockClient

_TRACE_WRITE = "backend.app.services.ai_trace_logger._write_to_db"


def _chunk(url="https://gov.example/x"):
    return {
        "source_url": url, "source_ref": url,
        "chunk_text": "A residence permit is required.",
        "trust_tier": 1, "fetched_at": "2026-06-06T00:00:00+00:00", "corridor": "FR_NO",
    }


def _payload(chunks):
    return {
        "chunks": chunks, "all_stale_warning": False,
        "oldest_fetched_at": chunks[0]["fetched_at"] if chunks else None,
    }


class ContextInjectionTests(unittest.TestCase):
    def setUp(self):
        p = mock.patch(_TRACE_WRITE)
        p.start()
        self.addCleanup(p.stop)

    def test_applicant_context_is_injected_into_system_prompt(self):
        url = "https://gov.example/x"
        mockc = MockClient(default_response=f"You need a residence permit [source: {url}].")
        res = generate_immigration_answer(
            _payload([_chunk(url)]), "What documents do I need?", "FR→NO",
            client=mockc, applicant_context="Long-term assignment; relocating with 2 dependent(s)",
        )
        sysp = mockc.calls[0].system
        self.assertIn("APPLICANT CONTEXT", sysp)
        self.assertIn("Long-term assignment; relocating with 2 dependent(s)", sysp)
        # Grounding is preserved: still a real, cited answer.
        self.assertEqual(res["answer_kind"], "answer")

    def test_no_context_leaves_system_prompt_unchanged(self):
        url = "https://gov.example/x"
        mockc = MockClient(default_response=f"ok [source: {url}].")
        generate_immigration_answer(_payload([_chunk(url)]), "q", "FR→NO", client=mockc)
        self.assertNotIn("APPLICANT CONTEXT", mockc.calls[0].system)

    def test_refusal_path_never_reaches_the_llm_even_with_context(self):
        mockc = MockClient(default_response="x")
        res = generate_immigration_answer(
            _payload([]), "q", "ZZ→XX", client=mockc, applicant_context="Long-term assignment",
        )
        self.assertEqual(res["answer_kind"], "refusal_insufficient_context")
        self.assertEqual(len(mockc.calls), 0)
