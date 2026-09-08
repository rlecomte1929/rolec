"""AIQ-1309 follow-up · Tests for the VISA_PERMIT extraction agent.

Mirrors the family-member extraction test pattern (test_family_member_extraction.py):
an in-memory registry + sink, a mock LLM completer, and assertions on the emitted
ExtractedField tuple. Covers:

1. Prompt loads from disk.
2. The agent is wired into EXTRACTION_AGENT_REGISTRY under VISA_PERMIT.
3. The filename classifier routes visa / work-permit names to VISA_PERMIT.
4. The agent emits the load-bearing fields (visa_type, expiry_date, ...).
5. Dates (issue_date / expiry_date) normalise to ISO yyyy-mm-dd.
6. A non-visa payload (is_visa_permit=false) yields no spurious fields.
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
    EXTRACTION_AGENT_REGISTRY,
    VISA_PERMIT_DOCUMENT_TYPE,
    VisaPermitAgent,
    get_extraction_agent_class,
    load_visa_permit_prompt,
)
from backend.app.services.rce_document_ingest import classify_rce_document_type
from backend.relopass.llm import register_completer, reset_registry
from backend.relopass.llm.router import CompletionResult, set_agent_run_logger


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — multilingual visa / work-permit payloads
# ─────────────────────────────────────────────────────────────────────────────

DE_BLUE_CARD = {
    "is_visa_permit": True,
    "visa_type": "EU Blue Card",
    "document_number": "DE-BC-99213",
    "visa_holder_name": "Hans Müller",
    "issue_date": "15.07.2023",
    "expiry_date": "14.07.2027",
    "issuing_country": "Bundesrepublik Deutschland",
    "entry_conditions": "employer-specific",
    "country_iso3": "DEU",
}

FR_VLS = {
    "is_visa_permit": True,
    "visa_type": "Visa long séjour (VLS-TS)",
    "document_number": "FR-2024-77821",
    "visa_holder_name": "Marc Dubois",
    "issue_date": "01/03/2024",
    "expiry_date": "28/02/2025",
    "issuing_country": "République française",
    "country_iso3": "FRA",
}

UK_SKILLED_WORKER = {
    "is_visa_permit": True,
    "visa_type": "Skilled Worker",
    "document_number": "BRP-RX1234567",
    "visa_holder_name": "Jane Smith",
    "issue_date": "2023-09-01",
    "expiry_date": "2026-09-01",
    "issuing_country": "United Kingdom",
    "entry_conditions": "no public funds",
    "country_iso3": "GBR",
}

ALL_VISA_FIXTURES = {
    "DE": DE_BLUE_CARD,
    "FR": FR_VLS,
    "UK": UK_SKILLED_WORKER,
}

NOT_A_VISA = {
    "is_visa_permit": False,
    "visa_type": None,
    "expiry_date": None,
}


def _document(text: str = "doc") -> ParsedDocument:
    return ParsedDocument(document_id=uuid4(), case_id=uuid4(), text=text)


def _install_completer(payload: Mapping[str, Any]) -> None:
    async def _completer(prompt: str, **_kwargs: Any) -> CompletionResult:
        return CompletionResult(
            text=json.dumps({"input": payload}, ensure_ascii=False),
            tokens_in=300,
            tokens_out=110,
        )

    register_completer("gpt-4o-mini", _completer)
    register_completer("claude-sonnet-4-6", _completer)


@pytest.fixture(autouse=True)
def _reset_state():
    reset_registry()
    set_agent_run_logger(None)
    yield
    reset_registry()
    set_agent_run_logger(None)


def _visa_agent():
    agent = VisaPermitAgent(
        registry=AgentRegistry(InMemoryAgentStorage()),
        sink=InMemoryExtractionSink(),
    )
    agent.register()
    return agent


# ─────────────────────────────────────────────────────────────────────────────
# Prompt loading + registry + classifier wiring
# ─────────────────────────────────────────────────────────────────────────────


def test_prompt_loads_from_disk():
    assert "VISA_PERMIT" in load_visa_permit_prompt()


def test_registry_wires_visa_permit():
    assert get_extraction_agent_class(VISA_PERMIT_DOCUMENT_TYPE) is VisaPermitAgent
    assert VISA_PERMIT_DOCUMENT_TYPE in EXTRACTION_AGENT_REGISTRY


@pytest.mark.parametrize(
    "file_name",
    [
        "schengen_visa.pdf",
        "work_permit_2024.png",
        "Aufenthaltstitel.jpg",
        "titre-de-sejour.pdf",
        "oppholdstillatelse.pdf",
        "uk_brp.png",
    ],
)
def test_classifier_routes_visa_permit(file_name):
    assert classify_rce_document_type(file_name) == "VISA_PERMIT"


def test_classifier_does_not_misroute_passport():
    # passport must still win (it is checked before visa/permit).
    assert classify_rce_document_type("passport_scan.jpg") == "PASSPORT_TD3"


# ─────────────────────────────────────────────────────────────────────────────
# Extraction — fields + date normalisation
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("locale", list(ALL_VISA_FIXTURES))
def test_visa_permit_extracts_all_fields(locale):
    payload = ALL_VISA_FIXTURES[locale]
    _install_completer(payload)
    agent = _visa_agent()
    result = asyncio.run(agent.run(_document()))

    by_key = {f.field_key: f for f in result.fields}
    for key in ("visa_type", "document_number", "visa_holder_name", "issuing_country"):
        assert key in by_key, f"{locale}: missing {key}"
        assert by_key[key].value_raw


@pytest.mark.parametrize("locale", list(ALL_VISA_FIXTURES))
def test_dates_normalised_to_iso(locale):
    payload = ALL_VISA_FIXTURES[locale]
    _install_completer(payload)
    agent = _visa_agent()
    result = asyncio.run(agent.run(_document()))

    by_key = {f.field_key: f for f in result.fields}
    for key in ("issue_date", "expiry_date"):
        assert key in by_key, f"{locale}: missing {key}"
        iso = by_key[key].value_raw
        assert iso.count("-") == 2 and len(iso) == 10, f"{locale}: {key} not ISO: {iso}"


def test_non_visa_payload_emits_no_fields():
    _install_completer(NOT_A_VISA)
    agent = _visa_agent()
    result = asyncio.run(agent.run(_document()))
    # is_visa_permit=false → every value null → make_field drops them all.
    assert result.fields == ()
