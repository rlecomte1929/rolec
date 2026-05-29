"""C1-13 · Tests for the deterministic LLM router (backend/relopass/llm/router.py).

Covers each Validation Criterion from the Notion task:

1. route_llm('document_classification') returns gpt-4o-mini handle.
2. route_llm('eligibility_reasoning') always returns claude-3-7-sonnet.
3. route_llm('extraction', confidence=0.7) escalates to claude-3-7-sonnet.
4. All §11 table rows implemented.
5. Cost logging visible in agent_runs after each call.
6. Test fixture asserts the deterministic routing decisions.

Pure-Python — no network, no SDK, no DB. The completer + agent_runs
logger are mocked via the registry hooks the router exposes.
"""

from __future__ import annotations

import asyncio
from typing import List

import pytest

from backend.relopass.llm import (
    LLMHandle,
    LLMRoutingError,
    ROUTING_TABLE,
    register_completer,
    reset_registry,
    route_llm,
)
from backend.relopass.llm.router import (
    AgentRunRecord,
    CompletionResult,
    is_no_model_handle,
    set_agent_run_logger,
    usd_cost,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_router_state():
    """Clean slate between tests so logger / completer state from one test
    can't leak into another.
    """
    reset_registry()
    set_agent_run_logger(None)
    yield
    reset_registry()
    set_agent_run_logger(None)


def _install_dummy_completer(model: str, *, tokens_in: int = 100, tokens_out: int = 50):
    async def _completer(prompt: str, **_kwargs):
        return CompletionResult(text=f"<{model}> {prompt[:20]}", tokens_in=tokens_in, tokens_out=tokens_out)

    register_completer(model, _completer)


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 1 — document_classification → gpt-4o-mini
# ─────────────────────────────────────────────────────────────────────────────


def test_document_classification_defaults_to_gpt_4o_mini():
    handle = route_llm("document_classification")
    assert handle.model_name == "gpt-4o-mini"
    assert handle.task_class == "document_classification"
    assert handle.escalated is False


def test_document_classification_escalates_below_threshold():
    handle = route_llm("document_classification", current_confidence=0.5)
    assert handle.model_name == "gpt-4o"
    assert handle.escalated is True
    assert handle.escalation_reason is not None
    assert "0.50" in handle.escalation_reason


def test_document_classification_stays_default_above_threshold():
    handle = route_llm("document_classification", current_confidence=0.95)
    assert handle.model_name == "gpt-4o-mini"
    assert handle.escalated is False


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 2 — eligibility_reasoning → always claude-3-7-sonnet
# ─────────────────────────────────────────────────────────────────────────────


def test_eligibility_reasoning_always_returns_claude():
    handle = route_llm("eligibility_reasoning")
    assert handle.model_name == "claude-3-7-sonnet"
    assert handle.escalated is False


def test_eligibility_reasoning_ignores_confidence_inputs():
    handle = route_llm("eligibility_reasoning", current_confidence=0.10, validator_failed=True)
    assert handle.model_name == "claude-3-7-sonnet"
    assert handle.escalated is False  # no escalation path defined


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 3 — extraction alias, confidence=0.7 → claude-3-7-sonnet
# ─────────────────────────────────────────────────────────────────────────────


def test_extraction_alias_escalates_below_0_85_threshold():
    handle = route_llm("extraction", current_confidence=0.7)
    assert handle.task_class == "field_extraction"  # alias resolved
    assert handle.model_name == "claude-3-7-sonnet"
    assert handle.escalated is True
    assert handle.escalation_reason is not None
    assert "0.70" in handle.escalation_reason


def test_field_extraction_validator_failure_escalates_even_when_confident():
    handle = route_llm("field_extraction", current_confidence=0.99, validator_failed=True)
    assert handle.model_name == "claude-3-7-sonnet"
    assert handle.escalation_reason == "validator failure"


def test_field_extraction_default_above_threshold():
    handle = route_llm("field_extraction", current_confidence=0.9)
    assert handle.model_name == "gpt-4o-mini"
    assert handle.escalated is False


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 4 — All §11 table rows implemented
# ─────────────────────────────────────────────────────────────────────────────


def test_routing_table_has_all_seven_section_11_rows():
    expected = {
        "document_classification",
        "mrz_extraction",
        "field_extraction",
        "entity_resolution_fallback",
        "eligibility_reasoning",
        "policy_clause_extraction",
        "pathway_conversational",
    }
    assert set(ROUTING_TABLE.keys()) == expected


def test_mrz_extraction_routes_to_no_model_sentinel():
    handle = route_llm("mrz_extraction")
    assert is_no_model_handle(handle)
    assert handle.task_class == "mrz_extraction"


def test_entity_resolution_fallback_escalates_on_tight_cluster():
    handle = route_llm("entity_resolution_fallback", cosine_gap=0.03)
    assert handle.model_name == "claude-3-7-sonnet"
    assert handle.escalated is True


def test_entity_resolution_fallback_default_on_wide_cluster():
    handle = route_llm("entity_resolution_fallback", cosine_gap=0.20)
    assert handle.model_name == "gpt-4o-mini"
    assert handle.escalated is False


def test_policy_clause_extraction_always_claude():
    handle = route_llm("policy_clause_extraction")
    assert handle.model_name == "claude-3-7-sonnet"


def test_pathway_conversational_escalates_on_explain_intent():
    handle = route_llm("pathway_conversational", intent="explain")
    assert handle.model_name == "claude-3-7-sonnet"
    assert handle.escalated is True
    assert handle.escalation_reason == "'explain' intent"


def test_pathway_conversational_escalates_on_sensitive_topic():
    handle = route_llm("pathway_conversational", sensitive_topic=True)
    assert handle.model_name == "claude-3-7-sonnet"
    assert handle.escalation_reason == "sensitive topic"


def test_pathway_conversational_default_on_chit_chat():
    handle = route_llm("pathway_conversational")
    assert handle.model_name == "gpt-4o-mini"
    assert handle.escalated is False


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 5 — Cost logging visible in agent_runs after each call
# ─────────────────────────────────────────────────────────────────────────────


def test_complete_writes_agent_run_record():
    captured: List[AgentRunRecord] = []
    set_agent_run_logger(captured.append)
    _install_dummy_completer("gpt-4o-mini", tokens_in=1_000, tokens_out=500)

    handle = route_llm("document_classification")
    asyncio.run(handle.complete("classify this doc", case_id="case-123"))

    assert len(captured) == 1
    record = captured[0]
    assert record.model_name == "gpt-4o-mini"
    assert record.task_class == "document_classification"
    assert record.tokens_in == 1_000
    assert record.tokens_out == 500
    assert record.case_id == "case-123"
    assert record.inputs_digest
    assert record.output_digest
    # gpt-4o-mini: 0.15/M in + 0.60/M out → 0.00015 + 0.00030 = 0.00045
    assert record.cost_usd == pytest.approx(0.00045, rel=1e-6)
    # Cost mirrored on the handle.
    assert handle.cost_usd == pytest.approx(0.00045, rel=1e-6)


def test_complete_raises_without_registered_completer():
    handle = route_llm("eligibility_reasoning")
    with pytest.raises(LLMRoutingError):
        asyncio.run(handle.complete("hello"))


def test_complete_on_no_model_handle_raises():
    handle = route_llm("mrz_extraction")
    with pytest.raises(LLMRoutingError):
        asyncio.run(handle.complete("doesn't apply"))


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 6 — Test fixture asserts the deterministic routing decisions
# ─────────────────────────────────────────────────────────────────────────────


# Canonical routing matrix derived from Architecture Report §11. Each row:
# (task_class, kwargs to route_llm) → (expected_model, expected_escalated)
ROUTING_MATRIX = [
    ("document_classification", {}, "gpt-4o-mini", False),
    ("document_classification", {"current_confidence": 0.95}, "gpt-4o-mini", False),
    ("document_classification", {"current_confidence": 0.5}, "gpt-4o", True),
    ("field_extraction", {}, "gpt-4o-mini", False),
    ("field_extraction", {"current_confidence": 0.7}, "claude-3-7-sonnet", True),
    ("field_extraction", {"validator_failed": True}, "claude-3-7-sonnet", True),
    ("extraction", {"current_confidence": 0.7}, "claude-3-7-sonnet", True),
    ("entity_resolution_fallback", {}, "gpt-4o-mini", False),
    ("entity_resolution_fallback", {"cosine_gap": 0.02}, "claude-3-7-sonnet", True),
    ("entity_resolution_fallback", {"cosine_gap": 0.30}, "gpt-4o-mini", False),
    ("eligibility_reasoning", {}, "claude-3-7-sonnet", False),
    ("policy_clause_extraction", {}, "claude-3-7-sonnet", False),
    ("pathway_conversational", {}, "gpt-4o-mini", False),
    ("pathway_conversational", {"intent": "explain"}, "claude-3-7-sonnet", True),
    ("pathway_conversational", {"sensitive_topic": True}, "claude-3-7-sonnet", True),
]


@pytest.mark.parametrize("task_class,kwargs,expected_model,expected_escalated", ROUTING_MATRIX)
def test_deterministic_routing_decisions(task_class, kwargs, expected_model, expected_escalated):
    handle = route_llm(task_class, **kwargs)
    assert handle.model_name == expected_model, (
        f"{task_class!r} with {kwargs} → {handle.model_name!r}, expected {expected_model!r}"
    )
    assert handle.escalated is expected_escalated


def test_unknown_task_class_raises():
    with pytest.raises(LLMRoutingError):
        route_llm("not_a_real_task")


def test_cost_table_supports_all_models_in_routing_table():
    # Every model in the routing table must be priced — otherwise route_llm
    # raises at call time. We validate up-front so this is hard to forget.
    for decision in ROUTING_TABLE.values():
        for model in (decision.default_model, decision.escalate_model):
            if model is None:
                continue
            # Will raise LLMRoutingError if missing.
            usd_cost(model, 0, 0)


def test_register_completer_replaces_existing():
    async def first(prompt: str, **_kwargs):
        return CompletionResult(text="first", tokens_in=1, tokens_out=1)

    async def second(prompt: str, **_kwargs):
        return CompletionResult(text="second", tokens_in=2, tokens_out=2)

    register_completer("gpt-4o-mini", first)
    register_completer("gpt-4o-mini", second)

    handle = route_llm("document_classification")
    out = asyncio.run(handle.complete("ping"))
    assert out == "second"
    assert handle.tokens_in == 2
