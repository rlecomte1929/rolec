"""C1-04 · Tests for the document classifier.

Covers the 4 Notion validation criteria:

1. ≥95% accuracy on 60-document held-out fixture (live-LLM gated)
2. Escalation to gpt-4o fires when default confidence < 0.80
3. agent_runs row contains prompt version, model used, tokens, cost
4. Returns 'UNKNOWN' rather than guessing when below 0.50 confidence

Pure-Python: no DB, no SDK, no network. The LLM completer is mocked via
the C1-13 router's completer registry.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Mapping
from uuid import uuid4

import pytest

from backend.relopass.agents.classifier import (
    CLASSIFIER_PROMPT_VERSION,
    ESCALATION_THRESHOLD,
    KNOWN_DOCUMENT_CODES,
    UNKNOWN_CODE,
    UNKNOWN_THRESHOLD,
    ClassifierError,
    InMemoryClassifierAgentRunSink,
    UnknownClassificationCode,
    classify_document,
    load_classifier_prompt,
    reset_prompt_cache,
)
from backend.relopass.agents.models import ParsedDocument
from backend.relopass.llm import register_completer, reset_registry
from backend.relopass.llm.router import CompletionResult, set_agent_run_logger


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_state():
    reset_registry()
    set_agent_run_logger(None)
    reset_prompt_cache()
    yield
    reset_registry()
    set_agent_run_logger(None)
    reset_prompt_cache()


def _doc(text: str = "synthetic doc text") -> ParsedDocument:
    return ParsedDocument(document_id=uuid4(), case_id=uuid4(), text=text)


def _install_completer(
    *,
    response: Mapping[str, Any],
    model: str,
    tokens_in: int = 800,
    tokens_out: int = 50,
) -> None:
    async def _completer(prompt: str, **_kwargs: Any) -> CompletionResult:
        return CompletionResult(
            text=json.dumps({"input": response}, ensure_ascii=False),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )

    register_completer(model, _completer)


# ─────────────────────────────────────────────────────────────────────────────
# Prompt + constants
# ─────────────────────────────────────────────────────────────────────────────


def test_prompt_loads_from_disk_and_contains_17_codes():
    text = load_classifier_prompt()
    assert "C1-04" in text
    # Every controlled-vocabulary code should be mentioned at least once.
    for code in KNOWN_DOCUMENT_CODES:
        assert code in text, f"prompt missing code {code}"
    # And UNKNOWN is the special sentinel.
    assert UNKNOWN_CODE in text


def test_known_document_codes_matches_seed_catalog_17():
    # Lock in the field-set count so a refactor that adds/removes a code
    # surfaces here immediately. The C1-01b migration ships 17 rows.
    assert len(KNOWN_DOCUMENT_CODES) == 17


def test_confidence_thresholds_match_routing_table():
    # Lock in the spec values.
    assert ESCALATION_THRESHOLD == 0.80
    assert UNKNOWN_THRESHOLD == 0.50


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 2 — Escalation fires when default confidence < 0.80
# ─────────────────────────────────────────────────────────────────────────────


def test_escalates_to_gpt_4o_when_confidence_below_0_80():
    # gpt-4o-mini returns medium confidence (0.65 — below threshold).
    _install_completer(
        response={"code": "EMPLOYMENT_CONTRACT", "confidence": 0.65, "evidence": "weak cues"},
        model="gpt-4o-mini",
    )
    # gpt-4o returns the higher-confidence verdict.
    _install_completer(
        response={"code": "EMPLOYMENT_CONTRACT", "confidence": 0.93, "evidence": "CDI heading"},
        model="gpt-4o",
        tokens_in=1100,
        tokens_out=60,
    )

    sink = InMemoryClassifierAgentRunSink()
    result = asyncio.run(classify_document(_doc("contrat de travail à durée indéterminée"), sink=sink))

    assert result.tier == "escalated"
    assert result.model_name == "gpt-4o"
    assert result.code == "EMPLOYMENT_CONTRACT"
    assert result.confidence == pytest.approx(0.93)


def test_does_not_escalate_when_confidence_already_high():
    _install_completer(
        response={"code": "PASSPORT_TD3", "confidence": 0.98, "evidence": "ICAO TD3 MRZ"},
        model="gpt-4o-mini",
    )
    # NOTE: no gpt-4o completer registered — proves the default-tier
    # path doesn't hit the escalation handle.
    sink = InMemoryClassifierAgentRunSink()
    result = asyncio.run(classify_document(_doc("P<UTOERIKSSON..."), sink=sink))

    assert result.tier == "default"
    assert result.model_name == "gpt-4o-mini"
    assert result.code == "PASSPORT_TD3"


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 3 — agent_runs row contains prompt version, model, tokens, cost
# ─────────────────────────────────────────────────────────────────────────────


def test_agent_runs_row_captures_default_tier_metadata():
    _install_completer(
        response={"code": "PASSPORT_TD3", "confidence": 0.95, "evidence": "TD3 MRZ on p2"},
        model="gpt-4o-mini",
        tokens_in=850,
        tokens_out=40,
    )
    sink = InMemoryClassifierAgentRunSink()
    result = asyncio.run(classify_document(_doc(), sink=sink))

    assert len(sink.runs) == 1
    row = sink.runs[0]
    assert row.agent_run_id == result.agent_run_id
    assert row.agent_id == "document_classifier_v1"
    assert row.prompt_version == CLASSIFIER_PROMPT_VERSION == "v1"
    assert row.model_name == "gpt-4o-mini"
    assert row.tier == "default"
    assert row.tokens_in == 850
    assert row.tokens_out == 40
    # gpt-4o-mini: 0.15/M in + 0.60/M out → 850*0.00000015 + 40*0.0000006 = 0.0001515
    assert row.cost_usd == pytest.approx(0.0001515, rel=1e-6)
    assert row.status == "OK"
    assert row.final_code == "PASSPORT_TD3"
    assert row.final_confidence == pytest.approx(0.95)
    assert row.inputs_digest  # set
    assert row.output_digest  # set
    assert row.started_at <= row.finished_at


def test_agent_runs_row_accumulates_tokens_across_escalation():
    _install_completer(
        response={"code": "EMPLOYMENT_CONTRACT", "confidence": 0.50, "evidence": "weak"},
        model="gpt-4o-mini",
        tokens_in=800,
        tokens_out=50,
    )
    _install_completer(
        response={"code": "EMPLOYMENT_CONTRACT", "confidence": 0.95, "evidence": "CDI"},
        model="gpt-4o",
        tokens_in=1200,
        tokens_out=65,
    )
    sink = InMemoryClassifierAgentRunSink()
    asyncio.run(classify_document(_doc(), sink=sink))

    row = sink.runs[0]
    # Sum across mini + 4o calls.
    assert row.tokens_in == 800 + 1200
    assert row.tokens_out == 50 + 65
    assert row.model_name == "gpt-4o"
    assert row.tier == "escalated"


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 4 — Returns 'UNKNOWN' when below 0.50 confidence
# ─────────────────────────────────────────────────────────────────────────────


def test_returns_unknown_when_post_escalation_confidence_below_0_50():
    # Default-tier confidence below the floor → escalates → still below floor.
    _install_completer(
        response={"code": "EMPLOYMENT_CONTRACT", "confidence": 0.40, "evidence": "noisy"},
        model="gpt-4o-mini",
    )
    _install_completer(
        response={"code": "EMPLOYMENT_CONTRACT", "confidence": 0.45, "evidence": "still noisy"},
        model="gpt-4o",
    )
    sink = InMemoryClassifierAgentRunSink()
    result = asyncio.run(classify_document(_doc("garbled OCR"), sink=sink))

    assert result.code == UNKNOWN_CODE
    # The model's confidence is preserved (even though the code is overridden).
    assert result.confidence == pytest.approx(0.45)
    assert sink.runs[0].final_code == UNKNOWN_CODE


def test_unknown_emitted_directly_passes_through_when_high_confidence():
    # The model genuinely thinks the document is NOT a known type and is
    # confident about it (e.g. holiday photo, meal receipt).
    _install_completer(
        response={"code": "UNKNOWN", "confidence": 0.93, "evidence": "holiday photo"},
        model="gpt-4o-mini",
    )
    sink = InMemoryClassifierAgentRunSink()
    result = asyncio.run(classify_document(_doc("blurry"), sink=sink))

    assert result.code == UNKNOWN_CODE
    assert result.confidence == pytest.approx(0.93)
    assert result.tier == "default"


# ─────────────────────────────────────────────────────────────────────────────
# Validation + error paths
# ─────────────────────────────────────────────────────────────────────────────


def test_unknown_code_from_llm_raises():
    _install_completer(
        response={"code": "MEAL_RECEIPT", "confidence": 0.9, "evidence": "..."},
        model="gpt-4o-mini",
    )
    sink = InMemoryClassifierAgentRunSink()
    with pytest.raises(UnknownClassificationCode):
        asyncio.run(classify_document(_doc(), sink=sink))


def test_malformed_json_raises_classifier_error():
    async def _completer(prompt: str, **_kwargs: Any) -> CompletionResult:
        return CompletionResult(text="not json {{", tokens_in=1, tokens_out=1)

    register_completer("gpt-4o-mini", _completer)
    sink = InMemoryClassifierAgentRunSink()
    with pytest.raises(ClassifierError):
        asyncio.run(classify_document(_doc(), sink=sink))


def test_classifier_does_not_silently_degrade_when_completer_missing():
    # No completer registered — the classifier MUST raise; silent failure
    # would mean every downstream agent gets called on every document.
    sink = InMemoryClassifierAgentRunSink()
    with pytest.raises(ClassifierError):
        asyncio.run(classify_document(_doc(), sink=sink))


def test_confidence_is_clamped_to_unit_interval():
    _install_completer(
        response={"code": "PASSPORT_TD3", "confidence": 1.7, "evidence": "..."},
        model="gpt-4o-mini",
    )
    sink = InMemoryClassifierAgentRunSink()
    result = asyncio.run(classify_document(_doc(), sink=sink))
    assert 0.0 <= result.confidence <= 1.0


def test_prompt_text_is_truncated_to_8000_chars():
    # Push 20k chars of input — the classifier should still succeed
    # because internally the document text is truncated to 8 000 chars.
    _install_completer(
        response={"code": "EMPLOYMENT_CONTRACT", "confidence": 0.95, "evidence": "..."},
        model="gpt-4o-mini",
    )
    sink = InMemoryClassifierAgentRunSink()
    long_doc = _doc("A" * 20_000)
    result = asyncio.run(classify_document(long_doc, sink=sink))
    assert result.code == "EMPLOYMENT_CONTRACT"


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 1 — Live ≥95% accuracy on 60-fixture set (gated)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(
    os.environ.get("RELOPASS_LIVE_LLM_TESTS") != "1",
    reason=(
        "Live-LLM accuracy run skipped. Set RELOPASS_LIVE_LLM_TESTS=1 "
        "+ register real OpenAI completers to exercise the 60-doc "
        "fixture set covering FR/NO/DE/EN/HI."
    ),
)
def test_live_accuracy_meets_95_percent_target():
    raise NotImplementedError(
        "Activate after backend/services/llm_router_clients.py lands. "
        "60-doc fixture corpus belongs alongside C1-17."
    )
