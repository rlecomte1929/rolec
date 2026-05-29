"""C1-05f · Tests for the EU_RESIDENCE_PERMIT agent.

Validation criteria:
1. ≥90 % accuracy on 4-fixture set (FR/DE/NO/ES)
2. TD1 MRZ check digits validated via C1-02
3. residence_purpose_code emitted as a controlled vocabulary value
4. validity_end > today validation surfaced as Finding when expired

Synthetic-only fixtures: TD1 MRZs hand-built with the same algorithm
the parser uses for check digits.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
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
    EU_RESIDENCE_PERMIT_AGENT_NAME,
    MRZ_FIELD_KEYS,
    RESIDENCE_PURPOSE_VOCABULARY,
    EuResidencePermitAgent,
    load_eu_residence_permit_prompt,
)
from backend.relopass.docs.mrz import compute_check_digit, parse_mrz
from backend.relopass.llm import register_completer, reset_registry
from backend.relopass.llm.router import CompletionResult, set_agent_run_logger


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic TD1 fixture builder
# ─────────────────────────────────────────────────────────────────────────────


def _build_td1(
    *,
    doc_class: str = "IR",   # 'IR' = residence permit ICAO convention
    issuing: str,
    surname: str,
    given: str,
    doc_number: str,
    nationality: str,
    dob: str,
    sex: str,
    expiry: str,
    optional1: str = "",
    optional2: str = "",
) -> str:
    """Construct a valid TD1 MRZ (3 lines × 30 chars) with correct check digits.

    Line 1: [doc_class:2][issuing:3][doc_number:9][doc_cd:1][optional1:15]
    Line 2: [dob:6][dob_cd:1][sex:1][expiry:6][expiry_cd:1][nationality:3]
            [optional2:11][composite_cd:1]
    Line 3: [name_field:30]
    """
    doc_padded = doc_number.upper().ljust(9, "<")[:9]
    doc_cd = compute_check_digit(doc_padded)
    optional1_padded = optional1.upper().ljust(15, "<")[:15]
    line1 = f"{doc_class}{issuing}{doc_padded}{doc_cd}{optional1_padded}"
    assert len(line1) == 30, f"line1 length {len(line1)}"

    dob_cd = compute_check_digit(dob)
    expiry_cd = compute_check_digit(expiry)
    optional2_padded = optional2.upper().ljust(11, "<")[:11]
    composite_input = (
        doc_padded + str(doc_cd) + optional1_padded + dob + str(dob_cd)
        + expiry + str(expiry_cd) + optional2_padded
    )
    composite_cd = compute_check_digit(composite_input)
    line2 = (
        f"{dob}{dob_cd}{sex}{expiry}{expiry_cd}{nationality}"
        f"{optional2_padded}{composite_cd}"
    )
    assert len(line2) == 30, f"line2 length {len(line2)}"

    name_field = f"{surname}<<{given}".upper().ljust(30, "<")[:30]
    return f"{line1}\n{line2}\n{name_field}"


DE_PERMIT_MRZ = _build_td1(
    issuing="DEU",
    surname="MUELLER",
    given="HANS",
    doc_number="N9876543",
    nationality="DEU",
    dob="780214",
    sex="M",
    expiry="301231",
)

FR_PERMIT_MRZ = _build_td1(
    issuing="FRA",
    surname="DUPONT",
    given="MARIE",
    doc_number="FR2024A12",
    nationality="IND",
    dob="900404",
    sex="F",
    expiry="301115",
)

NO_PERMIT_MRZ = _build_td1(
    issuing="NOR",
    surname="HANSEN",
    given="OLAV",
    doc_number="NO123456",
    nationality="NOR",
    dob="850701",
    sex="M",
    expiry="290815",
)

# Already-expired (1 January 2020) — used by the expiry-finding test.
EXPIRED_PERMIT_MRZ = _build_td1(
    issuing="ESP",
    surname="GARCIA",
    given="MARIA",
    doc_number="ES999999",
    nationality="PER",
    dob="820505",
    sex="F",
    expiry="200101",
)


# ─────────────────────────────────────────────────────────────────────────────
# Pytest fixtures
# ─────────────────────────────────────────────────────────────────────────────


def _document(text: str) -> ParsedDocument:
    return ParsedDocument(document_id=uuid4(), case_id=uuid4(), text=text)


def _install_completer(payload: Mapping[str, Any]) -> None:
    async def _completer(prompt: str, **_kwargs: Any) -> CompletionResult:
        return CompletionResult(
            text=json.dumps({"input": payload}, ensure_ascii=False),
            tokens_in=300,
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
def permit_agent():
    registry = AgentRegistry(InMemoryAgentStorage())
    sink = InMemoryExtractionSink()
    agent = EuResidencePermitAgent(registry=registry, sink=sink)
    agent.register()
    return agent, sink


# ─────────────────────────────────────────────────────────────────────────────
# Prompt + registry
# ─────────────────────────────────────────────────────────────────────────────


def test_prompt_loads_from_disk():
    text = load_eu_residence_permit_prompt()
    assert "EU_RESIDENCE_PERMIT" in text


def test_register_persists_via_c1_05a_registry():
    registry = AgentRegistry(InMemoryAgentStorage())
    sink = InMemoryExtractionSink()
    agent = EuResidencePermitAgent(registry=registry, sink=sink)
    r = agent.register()
    assert r.created_new_agent
    assert r.version.name == EU_RESIDENCE_PERMIT_AGENT_NAME


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 2 — TD1 MRZ validated via C1-02
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "fixture", [DE_PERMIT_MRZ, FR_PERMIT_MRZ, NO_PERMIT_MRZ], ids=["DE", "FR", "NO"]
)
def test_mrz_fields_match_parser_exactly(permit_agent, fixture):
    agent, sink = permit_agent
    _install_completer({"residence_purpose_code": "BLUE_CARD"})
    result = asyncio.run(
        agent.run(_document("synthetic body"), mrz_text=fixture, current_date=date(2026, 5, 29))
    )
    canonical = parse_mrz(fixture)
    assert result.mrz_parse.format == "TD1"
    mrz_fields = {f.field_key: f for f in result.fields if f.field_key in MRZ_FIELD_KEYS}
    for key in MRZ_FIELD_KEYS:
        canonical_val = getattr(canonical, key, None)
        if canonical_val is None:
            assert key not in mrz_fields
            continue
        assert key in mrz_fields, f"missing {key}"
        expected = (
            canonical_val.isoformat()
            if hasattr(canonical_val, "isoformat")
            else str(canonical_val)
        )
        assert mrz_fields[key].value_raw == expected


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 3 — residence_purpose_code controlled vocabulary
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("value", list(RESIDENCE_PURPOSE_VOCABULARY))
def test_residence_purpose_code_passes_through_when_valid(permit_agent, value):
    agent, sink = permit_agent
    _install_completer({"residence_purpose_code": value})
    result = asyncio.run(
        agent.run(_document("body"), mrz_text=DE_PERMIT_MRZ, current_date=date(2026, 5, 29))
    )
    assert result.residence_purpose_code == value


def test_unknown_purpose_falls_back_to_other(permit_agent):
    agent, sink = permit_agent
    _install_completer({"residence_purpose_code": "some_unmapped_label"})
    result = asyncio.run(
        agent.run(_document("body"), mrz_text=DE_PERMIT_MRZ, current_date=date(2026, 5, 29))
    )
    assert result.residence_purpose_code == "OTHER"
    purpose_field = next(
        f for f in result.fields if f.field_key == "residence_purpose_code"
    )
    canon = purpose_field.value_canonical or {}
    assert "BLUE_CARD" in (canon.get("controlled_vocabulary") or [])


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 4 — Expiry < today emits PERMIT_EXPIRED finding
# ─────────────────────────────────────────────────────────────────────────────


def test_expired_permit_emits_permit_expired_finding(permit_agent):
    agent, sink = permit_agent
    _install_completer({"residence_purpose_code": "BLUE_CARD"})
    result = asyncio.run(
        agent.run(
            _document("body"),
            mrz_text=EXPIRED_PERMIT_MRZ,
            current_date=date(2026, 5, 29),
        )
    )
    assert result.is_expired is True
    expiry_field = next(
        (f for f in result.fields if f.field_key == "permit_expired_finding"),
        None,
    )
    assert expiry_field is not None
    assert "PERMIT_EXPIRED" in (expiry_field.value_raw or "")
    assert expiry_field.resolution_status == "Requires attention"


def test_valid_permit_does_not_emit_expired_finding(permit_agent):
    agent, sink = permit_agent
    _install_completer({"residence_purpose_code": "BLUE_CARD"})
    result = asyncio.run(
        agent.run(
            _document("body"),
            mrz_text=DE_PERMIT_MRZ,
            current_date=date(2026, 5, 29),
        )
    )
    assert result.is_expired is False
    assert not any(
        f.field_key == "permit_expired_finding" for f in result.fields
    )


# ─────────────────────────────────────────────────────────────────────────────
# Auxiliary
# ─────────────────────────────────────────────────────────────────────────────


def test_agent_runs_row_carries_model_tokens_cost(permit_agent):
    agent, sink = permit_agent
    _install_completer({"residence_purpose_code": "BLUE_CARD"})
    asyncio.run(
        agent.run(_document("body"), mrz_text=DE_PERMIT_MRZ, current_date=date(2026, 5, 29))
    )
    assert len(sink.agent_runs) == 1
    assert sink.agent_runs[0].model_name == "gpt-4o-mini"


def test_run_proceeds_when_llm_router_has_no_completer(permit_agent):
    agent, sink = permit_agent
    result = asyncio.run(
        agent.run(_document("body"), mrz_text=DE_PERMIT_MRZ, current_date=date(2026, 5, 29))
    )
    assert result.model_name == "(none — LLM unrouted)"
    # MRZ fields still flowed (the deterministic layer).
    assert any(f.field_key == "surname" for f in result.fields)
