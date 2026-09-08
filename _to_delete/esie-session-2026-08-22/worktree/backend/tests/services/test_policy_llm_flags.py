"""
Tests for backend.core.llm_flags and its wiring into the policy LLM call sites.

Covers Prompt 0 GAP-006 / Prompt A §1 rule 1 with the recipe shapes:
- LLMDisabled is a frozen dataclass carrying a `reason` string.
- policy_llm_temperature(default=0.0) accepts a caller-provided fallback.
- Extractor returns empty facts; answerer returns "" when disabled.
- No OpenAI() construction happens when disabled.
- Temperature flows through to chat.completions.create when enabled.
"""
from __future__ import annotations

import os
import sys
from typing import Any
from unittest.mock import MagicMock

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

    def test_temperature_respects_caller_default(self) -> None:
        assert policy_llm_temperature(default=0.4) == 0.4

    def test_temperature_reads_float(self) -> None:
        os.environ["RELOPASS_POLICY_LLM_TEMPERATURE"] = "0.35"
        assert policy_llm_temperature() == 0.35

    def test_temperature_invalid_falls_back(self) -> None:
        os.environ["RELOPASS_POLICY_LLM_TEMPERATURE"] = "not-a-float"
        assert policy_llm_temperature(default=0.1) == 0.1


class TestLLMDisabledDataclass:
    def test_carries_reason(self) -> None:
        d = LLMDisabled(reason="RELOPASS_POLICY_LLM_DISABLED=1")
        assert d.reason == "RELOPASS_POLICY_LLM_DISABLED=1"

    def test_is_falsy(self) -> None:
        # Enables `if client:` branching into the deterministic path.
        assert bool(LLMDisabled(reason="test")) is False

    def test_isinstance_branch(self) -> None:
        d = LLMDisabled(reason="x")
        # `isinstance(client, LLMDisabled)` is the recipe's discriminator.
        assert isinstance(d, LLMDisabled)


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
        from backend.app.services.policy_canonical_extraction import (
            OpenAIPolicyCanonicalExtractor,
            PolicyFactExtractionLLMInput,
        )
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
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
        from backend.app.services.policy_query_answering import CanonicalPolicyQueryLLM
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
    """The configured temperature reaches the OpenAI client when LLM is enabled."""

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
        from backend.app.services.policy_canonical_extraction import (
            OpenAIPolicyCanonicalExtractor,
            PolicyFactExtractionLLMInput,
        )
        fake = self._fake_client()
        ext = OpenAIPolicyCanonicalExtractor(client=fake)
        llm_input = PolicyFactExtractionLLMInput(chunk_id="chunk-1", text_content="placeholder")
        ext.extract(llm_input)
        assert fake.chat.completions.create.call_args.kwargs["temperature"] == 0.3

    def test_answerer_forwards_temperature(self) -> None:
        from backend.app.services.policy_query_answering import CanonicalPolicyQueryLLM
        fake = self._fake_client(json_payload="template answer")
        fake.chat.completions.create.return_value.choices[0].message.content = "template"
        llm = CanonicalPolicyQueryLLM(client=fake)
        llm.answer(query="q", context_blocks=["ctx"])
        assert fake.chat.completions.create.call_args.kwargs["temperature"] == 0.3
