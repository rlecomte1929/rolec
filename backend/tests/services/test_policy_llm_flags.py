"""
Tests for backend.core.llm_flags and its wiring into the two policy LLM
call sites.

Covers audit Prompt 0 GAP-006 / Prompt A §1 rule 1:
- RELOPASS_POLICY_LLM_DISABLED turns off every policy LLM call without
  constructing an OpenAI client.
- RELOPASS_POLICY_LLM_TEMPERATURE flows through to chat.completions.create.
- Extractor returns empty facts, answerer returns empty string when disabled.
- No OpenAI() constructor is called when disabled, so no HTTP egress.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.core.llm_flags import (  # noqa: E402
    LLMDisabled,
    policy_llm_disabled,
    policy_llm_temperature,
)


class TestFlagParsing:
    def setup_method(self) -> None:
        self._saved = {
            "RELOPASS_POLICY_LLM_DISABLED": os.environ.get("RELOPASS_POLICY_LLM_DISABLED"),
            "RELOPASS_POLICY_LLM_TEMPERATURE": os.environ.get("RELOPASS_POLICY_LLM_TEMPERATURE"),
        }
        for k in self._saved:
            os.environ.pop(k, None)

    def teardown_method(self) -> None:
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_disabled_default_false(self) -> None:
        assert policy_llm_disabled() is False

    @pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "On", " on "])
    def test_disabled_truthy_values(self, raw: str) -> None:
        os.environ["RELOPASS_POLICY_LLM_DISABLED"] = raw
        assert policy_llm_disabled() is True

    @pytest.mark.parametrize("raw", ["0", "false", "no", "off", "", "maybe", "2"])
    def test_disabled_falsy_values(self, raw: str) -> None:
        os.environ["RELOPASS_POLICY_LLM_DISABLED"] = raw
        assert policy_llm_disabled() is False

    def test_temperature_default_zero(self) -> None:
        assert policy_llm_temperature() == 0.0

    def test_temperature_reads_float(self) -> None:
        os.environ["RELOPASS_POLICY_LLM_TEMPERATURE"] = "0.7"
        assert policy_llm_temperature() == 0.7

    def test_temperature_falls_back_on_garbage(self) -> None:
        os.environ["RELOPASS_POLICY_LLM_TEMPERATURE"] = "not-a-float"
        assert policy_llm_temperature() == 0.0


class TestSentinel:
    def test_repr_stable(self) -> None:
        assert repr(LLMDisabled) == "<LLMDisabled>"

    def test_is_falsy(self) -> None:
        # Enables `if client:` branching into the deterministic path.
        assert bool(LLMDisabled) is False


class TestExtractorShortCircuit:
    def setup_method(self) -> None:
        self._saved = os.environ.get("RELOPASS_POLICY_LLM_DISABLED")
        os.environ["RELOPASS_POLICY_LLM_DISABLED"] = "1"

    def teardown_method(self) -> None:
        if self._saved is None:
            os.environ.pop("RELOPASS_POLICY_LLM_DISABLED", None)
        else:
            os.environ["RELOPASS_POLICY_LLM_DISABLED"] = self._saved

    def test_extract_returns_empty_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.services.policy_canonical_extraction import (
            OpenAIPolicyCanonicalExtractor,
            PolicyFactExtractionLLMInput,
        )
        # Ensure no API key is set — if the disabled short-circuit fails,
        # the real OpenAI() constructor would still succeed with api_key=None
        # but chat.completions.create would raise. Either way, the test
        # would surface the regression loudly.
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # Also patch the lazy import so we detect any attempt to reach it.
        import openai as _openai_pkg  # noqa: F401 — ensures openai is importable
        call_count = {"n": 0}
        class _BoomClient:
            def __init__(self, *a, **kw):
                call_count["n"] += 1
                raise AssertionError("OpenAI() must not be constructed when disabled")
        monkeypatch.setattr("openai.OpenAI", _BoomClient)

        llm_input = PolicyFactExtractionLLMInput(chunk_id="chunk-1", text_content="placeholder")
        ext = OpenAIPolicyCanonicalExtractor()
        out = ext.extract(llm_input)
        assert call_count["n"] == 0
        assert out.facts == []


class TestAnswererShortCircuit:
    def setup_method(self) -> None:
        self._saved = os.environ.get("RELOPASS_POLICY_LLM_DISABLED")
        os.environ["RELOPASS_POLICY_LLM_DISABLED"] = "1"

    def teardown_method(self) -> None:
        if self._saved is None:
            os.environ.pop("RELOPASS_POLICY_LLM_DISABLED", None)
        else:
            os.environ["RELOPASS_POLICY_LLM_DISABLED"] = self._saved

    def test_answer_returns_empty_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.services.policy_query_answering import CanonicalPolicyQueryLLM
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        call_count = {"n": 0}
        class _BoomClient:
            def __init__(self, *a, **kw):
                call_count["n"] += 1
                raise AssertionError("OpenAI() must not be constructed when disabled")
        monkeypatch.setattr("openai.OpenAI", _BoomClient)

        llm = CanonicalPolicyQueryLLM()
        out = llm.answer(query="what is the cap?", context_blocks=["[1] cap is X"])
        assert call_count["n"] == 0
        assert out == ""


class TestTemperaturePassthrough:
    """
    When LLM is enabled, the configured temperature must reach the OpenAI
    client. Uses an injected fake client so no network call happens.
    """

    def setup_method(self) -> None:
        self._saved_disabled = os.environ.get("RELOPASS_POLICY_LLM_DISABLED")
        self._saved_temp = os.environ.get("RELOPASS_POLICY_LLM_TEMPERATURE")
        os.environ.pop("RELOPASS_POLICY_LLM_DISABLED", None)
        os.environ["RELOPASS_POLICY_LLM_TEMPERATURE"] = "0.3"

    def teardown_method(self) -> None:
        for k, v in (
            ("RELOPASS_POLICY_LLM_DISABLED", self._saved_disabled),
            ("RELOPASS_POLICY_LLM_TEMPERATURE", self._saved_temp),
        ):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _fake_client(self, json_payload: str = '{"facts": []}') -> Any:
        fake = MagicMock()
        resp = MagicMock()
        choice = MagicMock()
        choice.message.content = json_payload
        resp.choices = [choice]
        fake.chat.completions.create.return_value = resp
        return fake

    def test_extractor_forwards_temperature(self) -> None:
        from backend.services.policy_canonical_extraction import (
            OpenAIPolicyCanonicalExtractor,
            PolicyFactExtractionLLMInput,
        )
        fake = self._fake_client()
        ext = OpenAIPolicyCanonicalExtractor(client=fake)
        llm_input = PolicyFactExtractionLLMInput(
            chunk_id="chunk-1",
            text_content="placeholder",
        )
        ext.extract(llm_input)
        assert fake.chat.completions.create.call_args.kwargs["temperature"] == 0.3

    def test_answerer_forwards_temperature(self) -> None:
        from backend.services.policy_query_answering import CanonicalPolicyQueryLLM
        fake = self._fake_client(json_payload="template answer")
        fake.chat.completions.create.return_value.choices[0].message.content = "template"
        llm = CanonicalPolicyQueryLLM(client=fake)
        llm.answer(query="q", context_blocks=["ctx"])
        assert fake.chat.completions.create.call_args.kwargs["temperature"] == 0.3
