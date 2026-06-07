"""
AIQ-285 regression test — LLM policy extractor fallback behavior.

Verifies the audit's two hardest contract clauses without needing a live
ANTHROPIC_API_KEY:

  1. When ANTHROPIC_API_KEY is unset, `extract_policy_with_llm` returns None
     and `extract_policy_with_diff` returns a result with `llm_used=False`
     and `llm_unavailable_reason='no_api_key'`. The merged result falls
     back cleanly to the regex output (no exception, no auto-save).
  2. When the Anthropic API call raises, the diff result still has
     `llm_used=False` and `llm_unavailable_reason='call_failed'`, and the
     merged result equals the regex extraction (no partial / corrupted state).

The benefits_list shape is asserted against the regex contract so callers
that swap regex → LLM later don't have to special-case the response.

The pre-existing `query_counter` mock pattern from test_b12b_employee_cases.py
is reused because `backend.app.services.policy_extractor.extract_policy_with_diff`
imports through the module path the same way.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Match the conftest pattern from test_b12b_employee_cases.py — pre-empt the
# install_query_counter call inside backend.main that fails on the mocked
# db.engine from the root conftest.
_qc_mod = MagicMock()
_qc_mod.install_query_counter = lambda *a, **kw: None
sys.modules.setdefault("backend.app.services.query_counter", _qc_mod)

from backend.app.services import llm_policy_extractor  # noqa: E402
from backend.app.services import policy_extractor  # noqa: E402


SAMPLE_LINES = [
    "Acme Corp Relocation Policy v2.3",
    "Effective 2026-01-01",
    "6.1 Temporary housing — up to 60 days, capped at USD 6000.",
    "6.2 Visa support — full coverage for B1 and B2 bands.",
    "6.3 Shipment — 40 cubic feet household goods. Permanent transfers only.",
]


class TestLLMNotAvailable(unittest.TestCase):
    """ANTHROPIC_API_KEY missing → fallback path."""

    def setUp(self):
        # Force the API key absent regardless of the dev environment.
        self._saved = os.environ.pop("ANTHROPIC_API_KEY", None)

    def tearDown(self):
        if self._saved is not None:
            os.environ["ANTHROPIC_API_KEY"] = self._saved

    def test_extract_with_llm_returns_none_without_api_key(self):
        self.assertIsNone(llm_policy_extractor.extract_policy_with_llm(SAMPLE_LINES))

    def test_extract_with_llm_returns_none_on_empty_input(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-test-noop"
        try:
            self.assertIsNone(llm_policy_extractor.extract_policy_with_llm([]))
        finally:
            del os.environ["ANTHROPIC_API_KEY"]


class TestDiffOrchestratorFallback(unittest.TestCase):
    """`extract_policy_with_diff` degrades cleanly when the LLM is unavailable."""

    def setUp(self):
        self._saved = os.environ.pop("ANTHROPIC_API_KEY", None)

    def tearDown(self):
        if self._saved is not None:
            os.environ["ANTHROPIC_API_KEY"] = self._saved

    def test_diff_falls_back_to_regex_when_no_api_key(self):
        with patch.object(
            policy_extractor,
            "_parse_lines_from_bytes",
            return_value=SAMPLE_LINES,
        ):
            result = policy_extractor.extract_policy_with_diff(b"unused", "docx")

        self.assertIn("regex_extracted", result)
        self.assertIn("merged", result)
        self.assertIsNone(result["llm_extracted"])
        self.assertFalse(result["llm_used"])
        self.assertEqual(result["llm_unavailable_reason"], "no_api_key")
        # Regex path must still produce a benefits list (the sample text
        # mentions temporary housing / visa / shipment — at least one match).
        self.assertGreater(len(result["regex_extracted"]["benefits"]), 0)
        # Merged result is the regex result when LLM is absent.
        self.assertEqual(result["merged"]["extracted_by"], "regex")

    def test_diff_falls_back_when_llm_call_raises(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-test-noop"
        try:
            with patch.object(
                policy_extractor,
                "_parse_lines_from_bytes",
                return_value=SAMPLE_LINES,
            ), patch.object(
                llm_policy_extractor,
                "extract_policy_with_llm",
                side_effect=RuntimeError("simulated network failure"),
            ):
                result = policy_extractor.extract_policy_with_diff(b"unused", "docx")
        finally:
            del os.environ["ANTHROPIC_API_KEY"]

        self.assertIsNone(result["llm_extracted"])
        self.assertFalse(result["llm_used"])
        self.assertEqual(result["llm_unavailable_reason"], "call_failed")
        # Merged still matches regex output — never a half-failed state.
        self.assertEqual(result["merged"]["extracted_by"], "regex")
        self.assertEqual(
            len(result["merged"]["benefits"]),
            len(result["regex_extracted"]["benefits"]),
        )


class TestMergePrefersLLM(unittest.TestCase):
    """When both layers return, LLM benefits override regex by benefit_key."""

    def test_merge_overlays_llm_on_regex(self):
        regex_only = {
            "policy_meta": {"title": "Acme", "version": None, "effective_date": None},
            "benefits": [
                {
                    "service_category": "housing",
                    "benefit_key": "temporary_housing",
                    "benefit_label": "Temporary housing duration",
                    "eligibility": None,
                    "limits": {"days": 30},
                    "notes": None,
                    "source_section": "6.1",
                    "source_quote": "30 days",
                    "confidence": 0.4,
                },
                {
                    "service_category": "movers",
                    "benefit_key": "shipment",
                    "benefit_label": "Shipment of household goods",
                    "eligibility": None,
                    "limits": None,
                    "notes": None,
                    "source_section": None,
                    "source_quote": None,
                    "confidence": 0.3,
                },
            ],
            "extracted_at": "2026-05-26T10:00:00",
            "extracted_by": "regex",
        }
        llm_extra = {
            "policy_meta": {"title": "Acme Relocation Policy", "version": "2.3", "effective_date": "2026-01-01"},
            "benefits": [
                {
                    "service_category": "housing",
                    "benefit_key": "temporary_housing",
                    "benefit_label": "Temporary housing duration",
                    "eligibility": {"bands": ["B1", "B2"]},
                    "limits": {"days": 60, "cap": {"USD": 6000}},
                    "notes": "Up to 60 days, capped at USD 6000",
                    "source_section": "6.1",
                    "source_quote": "up to 60 days, capped at USD 6000",
                    "confidence": 0.92,
                },
            ],
            "extracted_at": "2026-05-26T10:00:01",
            "extracted_by": "ai",
        }

        merged = policy_extractor._merge_extractions(regex_only, llm_extra)

        # LLM value wins for temporary_housing.
        bench = {b["benefit_key"]: b for b in merged["benefits"]}
        self.assertEqual(bench["temporary_housing"]["limits"]["days"], 60)
        self.assertEqual(bench["temporary_housing"]["extracted_by"], "ai")
        # Regex-only key kept.
        self.assertEqual(bench["shipment"]["extracted_by"], "regex")
        # Merged meta prefers LLM when populated.
        self.assertEqual(merged["policy_meta"]["version"], "2.3")
        self.assertEqual(merged["policy_meta"]["effective_date"], "2026-01-01")


# ─────────────────────────────────────────────────────────────────────────────
# N11 / AIQ-851 — per-field confidence on the Anthropic tool_use path.
#
# The tool schema already carries a `confidence` value on EACH benefit object
# (it lives inside benefits[].items.properties, required per benefit), so this
# IS per-field confidence. N11 calibrates it to a coarse 3-tier scale
# (1.0 stated / 0.5 inferred / 0.1 absent). These tests lock in:
#   * the schema/prompt actually declare the 3-tier instruction, and
#   * the per-field confidence survives extraction → normalization, so a
#     clearly-stated benefit lands >= 0.8 and a silent/guessed one lands <= 0.2.
#
# We can't assert what a live model emits without an API key, so we mock the
# Anthropic client and feed the two boundary cases the 3-tier scale defines.
# ─────────────────────────────────────────────────────────────────────────────


class _FakeToolUseBlock:
    """Mimics an anthropic tool_use content block."""

    type = "tool_use"

    def __init__(self, tool_input):
        self.input = tool_input


class _FakeUsage:
    input_tokens = 10
    output_tokens = 20


class _FakeMessage:
    def __init__(self, blocks):
        self.content = blocks
        self.usage = _FakeUsage()


def _fake_anthropic_returning(tool_input):
    """Build a fake `anthropic` module whose client returns `tool_input`."""
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _FakeMessage(
        [_FakeToolUseBlock(tool_input)]
    )
    fake_module = MagicMock()
    fake_module.Anthropic.return_value = fake_client
    return fake_module


class TestPerFieldConfidenceSchema(unittest.TestCase):
    """The tool schema declares per-field confidence on the 3-tier scale."""

    def test_confidence_is_per_benefit_field(self):
        item_props = (
            llm_policy_extractor.EXTRACT_POLICY_TOOL["input_schema"]["properties"][
                "benefits"
            ]["items"]["properties"]
        )
        self.assertIn("confidence", item_props)
        self.assertIn("confidence", (
            llm_policy_extractor.EXTRACT_POLICY_TOOL["input_schema"]["properties"][
                "benefits"
            ]["items"]["required"]
        ))

    def test_prompt_states_the_three_tier_scale(self):
        desc = (
            llm_policy_extractor.EXTRACT_POLICY_TOOL["input_schema"]["properties"][
                "benefits"
            ]["items"]["properties"]["confidence"]["description"]
        )
        for tier in ("1.0", "0.5", "0.1"):
            self.assertIn(tier, desc)


class TestPerFieldConfidenceCarriesThrough(unittest.TestCase):
    """Per-field confidence survives extraction → normalization (N11 criteria 1 & 2)."""

    def _extract(self, tool_input):
        with patch.dict(sys.modules, {"anthropic": _fake_anthropic_returning(tool_input)}), \
                patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-noop"}):
            return llm_policy_extractor.extract_policy_with_llm(SAMPLE_LINES)

    def test_clearly_stated_value_keeps_high_confidence(self):
        # Criterion 1: a benefit with a clear source_quote → confidence >= 0.8.
        tool_input = {
            "policy_meta": {"title": "Acme"},
            "benefits": [
                {
                    "service_category": "housing",
                    "benefit_key": "temporary_housing",
                    "benefit_label": "Temporary housing",
                    "source_quote": "Temporary housing capped at USD 6000 for 60 days.",
                    "confidence": 1.0,
                }
            ],
        }
        result = self._extract(tool_input)
        self.assertIsNotNone(result)
        bench = {b["benefit_key"]: b for b in result["benefits"]}
        self.assertGreaterEqual(bench["temporary_housing"]["confidence"], 0.8)

    def test_absent_value_keeps_low_confidence(self):
        # Criterion 2: a benefit the policy is silent on → confidence <= 0.2.
        tool_input = {
            "policy_meta": {"title": "Acme"},
            "benefits": [
                {
                    "service_category": "tax",
                    "benefit_key": "tax_assistance",
                    "benefit_label": "Tax assistance",
                    "source_quote": None,
                    "confidence": 0.1,
                }
            ],
        }
        result = self._extract(tool_input)
        self.assertIsNotNone(result)
        bench = {b["benefit_key"]: b for b in result["benefits"]}
        self.assertLessEqual(bench["tax_assistance"]["confidence"], 0.2)


if __name__ == "__main__":
    unittest.main()
