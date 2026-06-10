"""Tests for the ID_CARD extraction agent (C2-02 / nationality source for C2-09).

The agent is MRZ-deterministic: given a TD1 ID-card MRZ it must surface
nationality_iso3 (and the other identity fields) verbatim from the parse. The
nationality field is the one C2-09's _compare_nationality cross-checks against
PASSPORT_TD3, so it is the load-bearing assertion here.
"""

from __future__ import annotations

from uuid import uuid4

from backend.relopass.agents import (
    AgentRegistry,
    InMemoryAgentStorage,
    ParsedDocument,
)
from backend.relopass.agents.runtime import InMemoryExtractionSink
from backend.relopass.agents.extraction import (
    EXTRACTION_AGENT_REGISTRY,
    ID_CARD_DOCUMENT_TYPE,
    IdCardAgent,
)
from backend.relopass.docs.mrz import compute_check_digit, parse_mrz


def _td1_fra() -> str:
    """A valid ICAO 9303 TD1 (3x30) ID-card MRZ, nationality FRA.

    Layout per mrz._parse_td1: line1 = 'I<' + issuing(3) + doc_number(9) +
    doc_cd(1) + optional pad; line2 = dob(6) + dob_cd + sex + expiry(6) +
    expiry_cd + nationality(3) + optional pad + composite_cd; line3 = name.
    """
    doc_padded = "SPEC12345".ljust(9, "<")
    doc_cd = compute_check_digit(doc_padded)
    line1 = f"I<FRA{doc_padded}{doc_cd}".ljust(30, "<")
    dob, expiry, sex, nat = "850315", "280620", "M", "FRA"
    dob_cd = compute_check_digit(dob)
    expiry_cd = compute_check_digit(expiry)
    line2 = f"{dob}{dob_cd}{sex}{expiry}{expiry_cd}{nat}".ljust(29, "<")
    line2 = f"{line2}{compute_check_digit(line2)}"
    line3 = "MARTIN<<JEAN<PAUL".ljust(30, "<")
    return f"{line1}\n{line2}\n{line3}"


def _make_agent() -> IdCardAgent:
    agent = IdCardAgent(
        registry=AgentRegistry(InMemoryAgentStorage()),
        sink=InMemoryExtractionSink(),
    )
    agent.register()
    return agent


def test_id_card_registered_in_extraction_registry():
    assert EXTRACTION_AGENT_REGISTRY[ID_CARD_DOCUMENT_TYPE] is IdCardAgent


def test_id_card_emits_nationality_iso3_from_td1_mrz():
    mrz_text = _td1_fra()
    # Sanity: the sample really is a parseable TD1 with FRA nationality.
    parsed = parse_mrz(mrz_text)
    assert parsed.format == "TD1", parsed.format
    assert parsed.nationality_iso3 == "FRA"

    agent = _make_agent()
    doc = ParsedDocument(document_id=uuid4(), case_id=uuid4(), text="")
    result = agent.run(doc, mrz_text=mrz_text)

    by_key = {f.field_key: f.value_raw for f in result.fields}
    assert by_key["nationality_iso3"] == "FRA"
    assert by_key["issuing_state_iso3"] == "FRA"
    assert by_key["document_number"].startswith("SPEC12345")


def test_id_card_nationality_field_present_for_c2_09_crosscheck():
    """C2-09 gathers field_key='nationality_iso3' across documents; the id_card
    agent must emit exactly that key so the comparator can pick it up."""
    agent = _make_agent()
    doc = ParsedDocument(document_id=uuid4(), case_id=uuid4(), text="")
    result = agent.run(doc, mrz_text=_td1_fra())
    keys = {f.field_key for f in result.fields}
    assert "nationality_iso3" in keys


def test_id_card_writes_agent_run_and_fields_to_sink():
    sink = InMemoryExtractionSink()
    agent = IdCardAgent(registry=AgentRegistry(InMemoryAgentStorage()), sink=sink)
    agent.register()
    doc = ParsedDocument(document_id=uuid4(), case_id=uuid4(), text="")
    agent.run(doc, mrz_text=_td1_fra())
    # The deterministic agent_run carries the MRZ model tag and zero cost.
    assert sink.agent_runs, "expected one agent_run row"
    run = sink.agent_runs[-1]
    assert run.model_name == "deterministic_mrz_icao9303"
    assert run.cost_usd == 0.0
