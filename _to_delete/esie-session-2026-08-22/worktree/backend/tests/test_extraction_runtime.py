"""C1-05a · Tests for the Extraction Agent runtime.

Covers each Validation Criterion from the Notion task:

1. ExtractionAgent persists to DB with all 9 fields.
2. Changing any of {extraction_instructions, value_type, unit,
   resolution_instructions, inconsistency_instructions,
   enable_complex_calculations_in_resolution, enable_web_search} or
   examples creates a new version row AND clears old extractions.
3. ExtractionRunner produces ExtractedField rows with non-null
   bbox_x0/y0/x1/y1 (0–1000).
4. agent_runs row written with model, tokens, cost.
5. Schema validation rejects outputs missing required field_keys.

Pure-Python — no DB, no network, no SDK. Storage is the in-memory
fake; the LLM completer is a mock registered with the C1-13 router.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Mapping
from uuid import uuid4

import pytest

from backend.relopass.agents import (
    AgentRegistry,
    ExtractionAgent,
    ExtractionAgentExample,
    ExtractionAgentVersion,
    ExtractionRunner,
    ExtractionRuntimeError,
    InMemoryAgentStorage,
    ParsedDocument,
    SchemaValidationError,
    VERSIONED_FIELDS,  # type: ignore[attr-defined]
)
from backend.relopass.agents.models import VERSIONED_FIELDS as _VF  # re-export check
from backend.relopass.agents.runtime import InMemoryExtractionSink
from backend.relopass.llm import register_completer, reset_registry
from backend.relopass.llm.router import (
    CompletionResult,
    set_agent_run_logger,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_global_state():
    reset_registry()
    set_agent_run_logger(None)
    yield
    reset_registry()
    set_agent_run_logger(None)


def _base_agent(**overrides: Any) -> ExtractionAgent:
    defaults: dict[str, Any] = dict(
        name="passport_td3.surname",
        description="Extract the surname from a TD3 passport MRZ.",
        extraction_instructions="Read the MRZ and return the surname field.",
        value_type="string",
        unit=None,
        dimensions=None,
        resolution_instructions=None,
        inconsistency_instructions=None,
        enable_web_search=False,
        enable_complex_calculations_in_resolution=False,
        examples=(),
        output_schema_required_keys=(),
    )
    defaults.update(overrides)
    return ExtractionAgent(**defaults)


def _install_completer_returning(output: Mapping[str, Any], *, tokens_in: int = 200, tokens_out: int = 80) -> None:
    """Register a deterministic completer for gpt-4o-mini (the default for
    field_extraction). Returns the provided JSON object on every call.
    """

    async def _completer(prompt: str, **_kwargs: Any) -> CompletionResult:
        return CompletionResult(
            text=json.dumps(output, ensure_ascii=False),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )

    register_completer("gpt-4o-mini", _completer)
    register_completer("claude-sonnet-4-6", _completer)


def _document(text: str = "Some document text.") -> ParsedDocument:
    return ParsedDocument(document_id=uuid4(), case_id=uuid4(), text=text)


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 1 — persistence with all 9 fields
# ─────────────────────────────────────────────────────────────────────────────


def test_save_agent_persists_all_nine_parsewise_fields():
    storage = InMemoryAgentStorage()
    registry = AgentRegistry(storage)
    agent = _base_agent(
        unit=None,
        dimensions="single-word string",
        resolution_instructions="If the MRZ surname is truncated, mark as ambiguous.",
        inconsistency_instructions="If MRZ surname differs from visual zone, prefer MRZ.",
        enable_web_search=False,
        enable_complex_calculations_in_resolution=False,
        examples=(
            ExtractionAgentExample(
                input_text="P<UTOERIKSSON<<ANNA<MARIA<...",
                output={"surname": "ERIKSSON"},
            ),
        ),
        output_schema_required_keys=("surname",),
    )

    result = registry.save_agent(agent)

    assert result.created_new_agent is True
    assert result.created_new_version is True
    v = result.version
    # All 9 Parsewise fields survive the persistence round trip.
    assert v.name == agent.name
    assert v.extraction_instructions == agent.extraction_instructions
    assert v.value_type == agent.value_type
    assert v.unit == agent.unit
    assert v.dimensions == agent.dimensions
    assert v.resolution_instructions == agent.resolution_instructions
    assert v.inconsistency_instructions == agent.inconsistency_instructions
    assert v.enable_web_search is agent.enable_web_search
    assert v.enable_complex_calculations_in_resolution is agent.enable_complex_calculations_in_resolution
    assert v.examples == agent.examples
    # Loading by name returns the same row.
    loaded = registry.load_current(agent.name)
    assert loaded.agent_version_id == v.agent_version_id


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 2 — Parsewise versioning rule
# ─────────────────────────────────────────────────────────────────────────────


def test_versioned_fields_list_matches_parsewise_spec():
    # Spec from the Notion brief + Architecture Report §4.1.
    expected = {
        "extraction_instructions",
        "value_type",
        "unit",
        "examples",
        "resolution_instructions",
        "inconsistency_instructions",
        "enable_complex_calculations_in_resolution",
        "enable_web_search",
    }
    assert set(_VF) == expected
    assert set(VERSIONED_FIELDS) == expected


@pytest.mark.parametrize(
    "field_name,changed_kwargs",
    [
        ("extraction_instructions", {"extraction_instructions": "Different instructions."}),
        ("value_type", {"value_type": "number"}),
        ("unit", {"value_type": "number", "unit": "EUR"}),  # unit only meaningful for numeric
        ("resolution_instructions", {"resolution_instructions": "Updated resolution."}),
        ("inconsistency_instructions", {"inconsistency_instructions": "Updated inconsistency rule."}),
        (
            "enable_complex_calculations_in_resolution",
            {"enable_complex_calculations_in_resolution": True},
        ),
        ("enable_web_search", {"enable_web_search": True}),
        (
            "examples",
            {
                "examples": (
                    ExtractionAgentExample(
                        input_text="ANOTHER MRZ", output={"surname": "DOE"}
                    ),
                )
            },
        ),
    ],
)
def test_changing_each_versioned_field_creates_new_version_and_clears_extractions(
    field_name, changed_kwargs
):
    storage = InMemoryAgentStorage()
    registry = AgentRegistry(storage)

    # v1
    agent_v1 = _base_agent()
    r1 = registry.save_agent(agent_v1)
    v1_id = r1.version.agent_version_id

    # Simulate a couple of extractions hanging off v1.
    storage.record_extraction(v1_id, uuid4())
    storage.record_extraction(v1_id, uuid4())
    storage.record_extraction(v1_id, uuid4())
    assert len(storage.extractions_by_version[v1_id]) == 3

    # v2 — change one versioned field.
    agent_v2 = _base_agent(**changed_kwargs)
    r2 = registry.save_agent(agent_v2)

    assert r2.created_new_agent is False
    assert r2.created_new_version is True
    assert r2.version.version_number == 2
    assert r2.cleared_extractions_for_prior_version_id == v1_id
    assert r2.cleared_extraction_count == 3
    assert field_name in r2.changed_fields
    # Confirm storage actually wiped them.
    assert storage.extractions_by_version[v1_id] == []
    # current_version advanced.
    assert storage.get_current_version_id(r1.agent_id) == r2.version.agent_version_id


def test_changing_only_non_versioned_field_is_a_noop():
    storage = InMemoryAgentStorage()
    registry = AgentRegistry(storage)

    r1 = registry.save_agent(_base_agent(description="First description"))
    v1_id = r1.version.agent_version_id

    storage.record_extraction(v1_id, uuid4())
    assert len(storage.extractions_by_version[v1_id]) == 1

    # `description` + `dimensions` + `output_schema_required_keys` are
    # NOT in VERSIONED_FIELDS; mutating them must not create a new version.
    r2 = registry.save_agent(
        _base_agent(
            description="Different description",
            dimensions="updated dimensions",
            output_schema_required_keys=("surname",),
        )
    )

    assert r2.created_new_version is False
    assert r2.version.agent_version_id == v1_id
    assert r2.cleared_extraction_count == 0
    # Extractions untouched.
    assert len(storage.extractions_by_version[v1_id]) == 1


def test_save_with_identical_versioned_fields_is_idempotent():
    storage = InMemoryAgentStorage()
    registry = AgentRegistry(storage)

    r1 = registry.save_agent(_base_agent())
    r2 = registry.save_agent(_base_agent())
    assert r1.version.agent_version_id == r2.version.agent_version_id
    assert r2.created_new_version is False


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 3 — ExtractedField rows carry 0-1000 bbox citations
# ─────────────────────────────────────────────────────────────────────────────


def test_extraction_run_produces_fields_with_canonical_bboxes():
    storage = InMemoryAgentStorage()
    registry = AgentRegistry(storage)
    agent_version = registry.save_agent(
        _base_agent(output_schema_required_keys=("surname",))
    ).version

    _install_completer_returning(
        {
            "fields": {
                "surname": {
                    "value": "ERIKSSON",
                    "confidence": 0.93,
                    "bbox": {"page": 1, "x0": 100, "y0": 200, "x1": 350, "y1": 220},
                }
            }
        }
    )

    sink = InMemoryExtractionSink()
    runner = ExtractionRunner(sink=sink)
    result = asyncio.run(runner.run(agent_version, _document()))

    assert len(result.fields) == 1
    field = result.fields[0]
    assert field.field_key == "surname"
    assert field.value_raw == "ERIKSSON"
    assert field.confidence == pytest.approx(0.93)
    # All four bbox edges populated and inside 0-1000.
    assert field.bbox_page == 1
    assert 0 <= field.bbox_x0 <= 1000
    assert 0 <= field.bbox_y0 <= 1000
    assert 0 <= field.bbox_x1 <= 1000
    assert 0 <= field.bbox_y1 <= 1000
    assert field.agent_run_id == result.agent_run_id


def test_extracted_field_rejects_out_of_range_bbox():
    # Hard guard at the Pydantic layer — values outside 0-1000 raise on construction.
    from backend.relopass.agents.models import ExtractedField

    with pytest.raises(Exception):  # ValidationError, not exposed cleanly across pydantic versions
        ExtractedField(
            document_id=uuid4(),
            field_key="foo",
            confidence=0.5,
            bbox_x0=-5,  # out of range
            bbox_y0=0,
            bbox_x1=10,
            bbox_y1=10,
        )

    with pytest.raises(Exception):
        ExtractedField(
            document_id=uuid4(),
            field_key="foo",
            confidence=0.5,
            bbox_x0=0,
            bbox_y0=0,
            bbox_x1=1500,  # over 1000
            bbox_y1=10,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 4 — agent_runs row carries model + tokens + cost
# ─────────────────────────────────────────────────────────────────────────────


def test_extraction_run_writes_agent_run_row():
    storage = InMemoryAgentStorage()
    registry = AgentRegistry(storage)
    agent_version = registry.save_agent(
        _base_agent(output_schema_required_keys=("surname",))
    ).version

    _install_completer_returning(
        {
            "fields": {
                "surname": {
                    "value": "ERIKSSON",
                    "confidence": 0.99,
                    "bbox": {"page": 1, "x0": 100, "y0": 200, "x1": 350, "y1": 220},
                }
            }
        },
        tokens_in=1000,
        tokens_out=400,
    )

    sink = InMemoryExtractionSink()
    runner = ExtractionRunner(sink=sink)
    result = asyncio.run(runner.run(agent_version, _document()))

    assert len(sink.agent_runs) == 1
    row = sink.agent_runs[0]
    assert row.agent_run_id == result.agent_run_id
    assert row.agent_version_id == agent_version.agent_version_id
    assert row.model_name == "gpt-4o-mini"
    assert row.tokens_in == 1000
    assert row.tokens_out == 400
    # gpt-4o-mini: 0.15/M in + 0.60/M out → 1000*0.00000015 + 400*0.0000006 = 0.00039
    assert row.cost_usd == pytest.approx(0.00039, rel=1e-6)
    assert row.status == "OK"
    assert row.started_at <= row.finished_at


def test_extraction_run_also_forwards_to_router_agent_run_logger():
    # When the router's pluggable logger is installed, the run is also
    # observable from that callback. This is the path C1-01's
    # rce.agent_runs writer will hook into.
    captured = []
    set_agent_run_logger(captured.append)

    storage = InMemoryAgentStorage()
    registry = AgentRegistry(storage)
    agent_version = registry.save_agent(
        _base_agent(output_schema_required_keys=("surname",))
    ).version

    _install_completer_returning(
        {
            "fields": {
                "surname": {
                    "value": "ERIKSSON",
                    "confidence": 0.99,
                    "bbox": {"page": 1, "x0": 100, "y0": 200, "x1": 350, "y1": 220},
                }
            }
        }
    )

    sink = InMemoryExtractionSink()
    runner = ExtractionRunner(sink=sink)
    asyncio.run(runner.run(agent_version, _document()))

    assert len(captured) == 1
    rec = captured[0]
    assert rec.model_name == "gpt-4o-mini"
    assert rec.task_class == "field_extraction"
    assert rec.tokens_in > 0
    assert rec.tokens_out > 0
    assert rec.cost_usd > 0


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 5 — Schema validation rejects outputs missing required keys
# ─────────────────────────────────────────────────────────────────────────────


def test_extraction_run_raises_on_missing_required_keys():
    storage = InMemoryAgentStorage()
    registry = AgentRegistry(storage)
    agent_version = registry.save_agent(
        _base_agent(output_schema_required_keys=("surname", "given_name"))
    ).version

    # LLM emits only one of the two required keys, twice (retry path also fails).
    _install_completer_returning(
        {
            "fields": {
                "surname": {
                    "value": "ERIKSSON",
                    "confidence": 0.95,
                    "bbox": {"page": 1, "x0": 1, "y0": 1, "x1": 10, "y1": 10},
                }
            }
        }
    )

    sink = InMemoryExtractionSink()
    runner = ExtractionRunner(sink=sink)

    with pytest.raises(SchemaValidationError) as exc:
        asyncio.run(runner.run(agent_version, _document()))
    assert "given_name" in str(exc.value)
    # No agent_run / extracted_field rows persisted on validation failure.
    assert sink.agent_runs == []
    assert sink.extracted_fields == []


def test_extraction_run_retries_with_escalated_model_on_first_validator_miss():
    """When the first attempt misses a required key, the runner re-routes
    with validator_failed=True (escalates to claude-sonnet-4-6 per §11) and
    succeeds on the second try.
    """
    storage = InMemoryAgentStorage()
    registry = AgentRegistry(storage)
    agent_version = registry.save_agent(
        _base_agent(output_schema_required_keys=("surname",))
    ).version

    # First call (gpt-4o-mini) emits an empty fields object → missing key.
    # Second call (escalated to claude-sonnet-4-6) emits the right field.
    call_count = {"n": 0}

    async def _completer_mini(prompt: str, **_kwargs: Any) -> CompletionResult:
        call_count["n"] += 1
        return CompletionResult(
            text=json.dumps({"fields": {}}),  # missing
            tokens_in=10,
            tokens_out=2,
        )

    async def _completer_claude(prompt: str, **_kwargs: Any) -> CompletionResult:
        call_count["n"] += 1
        return CompletionResult(
            text=json.dumps(
                {
                    "fields": {
                        "surname": {
                            "value": "ERIKSSON",
                            "confidence": 0.97,
                            "bbox": {"page": 1, "x0": 1, "y0": 1, "x1": 10, "y1": 10},
                        }
                    }
                }
            ),
            tokens_in=50,
            tokens_out=20,
        )

    register_completer("gpt-4o-mini", _completer_mini)
    register_completer("claude-sonnet-4-6", _completer_claude)

    sink = InMemoryExtractionSink()
    runner = ExtractionRunner(sink=sink)
    result = asyncio.run(runner.run(agent_version, _document()))

    assert result.model_name == "claude-sonnet-4-6"
    assert call_count["n"] == 2  # one mini, one claude
    assert len(sink.agent_runs) == 1  # only the successful run logged
    assert sink.agent_runs[0].model_name == "claude-sonnet-4-6"


def test_extraction_run_raises_on_malformed_json():
    storage = InMemoryAgentStorage()
    registry = AgentRegistry(storage)
    agent_version = registry.save_agent(_base_agent()).version

    async def _completer(prompt: str, **_kwargs: Any) -> CompletionResult:
        return CompletionResult(text="not json {{", tokens_in=5, tokens_out=5)

    register_completer("gpt-4o-mini", _completer)

    sink = InMemoryExtractionSink()
    runner = ExtractionRunner(sink=sink)

    with pytest.raises(ExtractionRuntimeError):
        asyncio.run(runner.run(agent_version, _document()))
