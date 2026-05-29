"""C1-05e · Tests for the DIPLOMA agent.

Validation criteria:
1. ≥90 % accuracy on 6-fixture set (mocked)
2. Devanagari preserved in name_native; Latin transliteration in institution_name
3. ISCED level inferred correctly (Bachelor → 6, Master → 7, Doctorate → 8)
4. anabin lookup deferred — emitted as null + pending_external_lookup
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Mapping
from uuid import uuid4

import pytest

from backend.relopass.agents import (
    AgentRegistry,
    InMemoryAgentStorage,
    ParsedDocument,
)
from backend.relopass.agents.runtime import InMemoryExtractionSink
from backend.relopass.agents.extraction import (
    DIPLOMA_AGENT_NAME,
    DiplomaAgent,
    infer_isced_level_from_title,
    load_diploma_prompt,
)
from backend.relopass.llm import register_completer, reset_registry
from backend.relopass.llm.router import CompletionResult, set_agent_run_logger


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


FR_LICENCE_TEXT = """
UNIVERSITÉ DE PARIS
DIPLÔME DE LICENCE
M. Pierre Martin a obtenu la Licence en Informatique
le 30 juin 2023.
"""

DE_BACHELOR_TEXT = """
TECHNISCHE UNIVERSITÄT MÜNCHEN
Bachelor of Science in Informatik
verliehen an Frau Anna Müller
am 15. Juli 2024.
"""

IN_BTECH_TEXT = """
BHARATIYA VIDYAPEETH UNIVERSITY (भारतीय विद्यापीठ विश्वविद्यालय)
Bachelor of Technology (B.Tech) in Computer Science
awarded to Priya Sharma (प्रिया शर्मा)
on 05 July 2022.
"""


def _document(text: str) -> ParsedDocument:
    return ParsedDocument(document_id=uuid4(), case_id=uuid4(), text=text)


def _install_completer(payload: Mapping[str, Any]) -> None:
    async def _completer(prompt: str, **_kwargs: Any) -> CompletionResult:
        return CompletionResult(
            text=json.dumps({"input": payload}, ensure_ascii=False),
            tokens_in=320,
            tokens_out=120,
        )

    register_completer("gpt-4o-mini", _completer)
    register_completer("claude-3-7-sonnet", _completer)


@pytest.fixture(autouse=True)
def _reset_state():
    reset_registry()
    set_agent_run_logger(None)
    yield
    reset_registry()
    set_agent_run_logger(None)


@pytest.fixture
def diploma_agent():
    registry = AgentRegistry(InMemoryAgentStorage())
    sink = InMemoryExtractionSink()
    agent = DiplomaAgent(registry=registry, sink=sink)
    agent.register()
    return agent, sink


# ─────────────────────────────────────────────────────────────────────────────
# Prompt + registry
# ─────────────────────────────────────────────────────────────────────────────


def test_prompt_loads_from_disk():
    text = load_diploma_prompt()
    assert "DIPLOMA" in text
    assert "ISCED" in text


def test_register_persists_via_c1_05a_registry():
    registry = AgentRegistry(InMemoryAgentStorage())
    sink = InMemoryExtractionSink()
    agent = DiplomaAgent(registry=registry, sink=sink)
    r = agent.register()
    assert r.created_new_agent
    assert r.version.name == DIPLOMA_AGENT_NAME


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 3 — ISCED inference
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Bachelor of Science in Computer Science", 6),
        ("Bachelor of Engineering", 6),
        ("Licence en Informatique", 6),
        ("Master of Science in Data Science", 7),
        ("Master of Business Administration", 7),
        ("MBA", 7),
        ("Magister", 7),
        ("Doctorat en Informatique", 8),
        ("PhD in Computer Science", 8),
        ("Doctor of Philosophy", 8),
        ("BTS Informatique", 5),
        ("DUT Réseaux", 5),
        ("Foundation degree", 5),
    ],
)
def test_isced_inference_from_title(title, expected):
    assert infer_isced_level_from_title(title) == expected


def test_isced_inference_returns_none_when_title_unclear():
    assert infer_isced_level_from_title(None) is None
    assert infer_isced_level_from_title("") is None
    assert infer_isced_level_from_title("Certificate of attendance") is None


def test_agent_takes_isced_from_llm_when_provided(diploma_agent):
    agent, sink = diploma_agent
    _install_completer(
        {
            "is_diploma": True,
            "institution_name": "Université de Paris",
            "qualification_title": "Licence en Informatique",
            "isced_level": 6,
            "award_date": "30/06/2023",
            "field_of_study": "Informatique",
            "country_iso3": "FRA",
        }
    )
    result = asyncio.run(agent.run(_document(FR_LICENCE_TEXT)))
    assert result.isced_level == 6
    assert result.isced_inference_source == "llm"


def test_agent_falls_back_to_title_inference_when_llm_omits_isced(diploma_agent):
    agent, sink = diploma_agent
    _install_completer(
        {
            "is_diploma": True,
            "institution_name": "Technische Universität München",
            "qualification_title": "Bachelor of Science in Informatik",
            # isced_level omitted on purpose
            "award_date": "15.07.2024",
            "field_of_study": "Informatik",
            "country_iso3": "DEU",
        }
    )
    result = asyncio.run(agent.run(_document(DE_BACHELOR_TEXT)))
    assert result.isced_level == 6
    assert result.isced_inference_source == "title_fallback"
    isced_field = next(f for f in result.fields if f.field_key == "isced_level")
    assert (isced_field.value_canonical or {}).get("inference_source") == "title_fallback"


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 2 — Devanagari handling
# ─────────────────────────────────────────────────────────────────────────────


def test_devanagari_institution_name_preserved_in_name_native(diploma_agent):
    agent, sink = diploma_agent
    _install_completer(
        {
            "is_diploma": True,
            "institution_name": "Bharatiya Vidyapeeth University",
            "institution_name_native": "भारतीय विद्यापीठ विश्वविद्यालय",
            "native_script": "Devanagari",
            "qualification_title": "Bachelor of Technology (B.Tech) in Computer Science",
            "isced_level": 6,
            "award_date": "2022-07-05",
            "field_of_study": "Computer Science",
            "country_iso3": "IND",
        }
    )
    result = asyncio.run(agent.run(_document(IN_BTECH_TEXT)))
    native_field = next(
        f for f in result.fields if f.field_key == "institution_name_native"
    )
    assert "भारतीय" in (native_field.value_raw or "")
    assert (native_field.value_canonical or {}).get("script") == "Devanagari"
    # Latin form sits in the standard institution_name field.
    latin_field = next(f for f in result.fields if f.field_key == "institution_name")
    assert "Bharatiya" in (latin_field.value_raw or "")


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 4 — anabin deferred to EXTERNAL_LOOKUP
# ─────────────────────────────────────────────────────────────────────────────


def test_anabin_emitted_as_null_with_pending_external_lookup(diploma_agent):
    agent, sink = diploma_agent
    _install_completer(
        {
            "is_diploma": True,
            "institution_name": "Université de Paris",
            "qualification_title": "Licence en Informatique",
            "isced_level": 6,
            "country_iso3": "FRA",
        }
    )
    result = asyncio.run(agent.run(_document(FR_LICENCE_TEXT)))
    anabin_field = next(
        f for f in result.fields if f.field_key == "recognized_in_anabin"
    )
    canon = anabin_field.value_canonical or {}
    assert canon.get("status") == "pending_external_lookup"
    assert canon.get("pattern") == "EXTERNAL_LOOKUP"
    assert anabin_field.resolution_status == "Not resolved"


# ─────────────────────────────────────────────────────────────────────────────
# Auxiliary
# ─────────────────────────────────────────────────────────────────────────────


def test_agent_runs_row_carries_model_tokens_cost(diploma_agent):
    agent, sink = diploma_agent
    _install_completer(
        {
            "is_diploma": True,
            "institution_name": "Université de Paris",
            "qualification_title": "Licence",
            "country_iso3": "FRA",
        }
    )
    asyncio.run(agent.run(_document(FR_LICENCE_TEXT)))
    assert len(sink.agent_runs) == 1
    row = sink.agent_runs[0]
    assert row.model_name == "gpt-4o-mini"
    assert row.tokens_in == 320
    assert row.tokens_out == 120


def test_run_proceeds_when_llm_router_has_no_completer(diploma_agent):
    agent, sink = diploma_agent
    result = asyncio.run(agent.run(_document(FR_LICENCE_TEXT)))
    assert result.model_name == "(none — LLM unrouted)"
