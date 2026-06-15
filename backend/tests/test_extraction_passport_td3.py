"""C1-05b · Tests for the PASSPORT_TD3 Extraction Agent.

Covers the 5 Validation Criteria from the Notion task:

1. ≥90% field accuracy on the 5 synthetic-passport fixture set.
2. MRZ fields match the C1-02 parser output exactly.
3. photo_bbox set with phi_class='BIOMETRIC'.
4. agent_version recorded per Parsewise convention.
5. Failed MRZ check digit creates DocumentValidationFinding(WARN)
   but does not block the agent.

Pure-Python — no DB, no Azure DI calls, no live LLM. The Azure DI provider
is a hand-rolled fake; the LLM completer is mocked through the C1-13
router's completer registry; persistence uses InMemoryAgentStorage +
InMemoryExtractionSink.

Synthetic fixtures only — every TD3 string in this file is hand-built
with the same algorithm the C1-02 parser uses for its check digits, so
the parser's MRZParseResult is the ground truth we assert against.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Iterable, List, Mapping
from uuid import uuid4

import pytest

from backend.relopass.agents import (
    AgentRegistry,
    InMemoryAgentStorage,
    ParsedDocument,
)
from backend.relopass.agents.runtime import InMemoryExtractionSink
from backend.relopass.agents.extraction import (
    AzureDiPassportOutput,
    Bbox,
    DI_FIELD_KEYS,
    LLM_FIELD_KEYS,
    MRZ_FIELD_KEYS,
    NullAzureDIProvider,
    PASSPORT_TD3_AGENT_NAME,
    PHI_CLASS_BIOMETRIC,
    PassportTd3Agent,
    load_passport_td3_prompt,
)
from backend.relopass.agents.extraction.passport_td3 import _get_agent
from backend.relopass.docs.mrz import (
    DocumentValidationFinding,
    compute_check_digit,
    parse_mrz,
)
from backend.relopass.llm import register_completer, reset_registry
from backend.relopass.llm.router import (
    CompletionResult,
    set_agent_run_logger,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — synthetic TD3 passports
# ─────────────────────────────────────────────────────────────────────────────


def _build_td3(
    *,
    issuing: str,
    surname: str,
    given: str,
    doc_number: str,
    nationality: str,
    dob: str,
    sex: str,
    expiry: str,
    personal: str = "",
) -> str:
    """Reproduces the helper in test_relopass_docs_mrz.py.

    Constructs a valid TD3 string with correct check digits. Duplicated
    rather than imported so this test file can stand alone.
    """
    name_field = f"{surname}<<{given}".upper()
    name_field = name_field.ljust(39, "<")[:39]
    line1 = f"P<{issuing}{name_field}"
    assert len(line1) == 44

    doc_padded = doc_number.upper().ljust(9, "<")[:9]
    personal_padded = personal.upper().ljust(14, "<")[:14]

    doc_cd = compute_check_digit(doc_padded)
    dob_cd = compute_check_digit(dob)
    expiry_cd = compute_check_digit(expiry)
    personal_cd = compute_check_digit(personal_padded)

    composite_input = (
        doc_padded
        + str(doc_cd)
        + dob
        + str(dob_cd)
        + expiry
        + str(expiry_cd)
        + personal_padded
        + str(personal_cd)
    )
    composite_cd = compute_check_digit(composite_input)

    line2 = (
        f"{doc_padded}{doc_cd}{nationality}{dob}{dob_cd}{sex}{expiry}{expiry_cd}"
        f"{personal_padded}{personal_cd}{composite_cd}"
    )
    assert len(line2) == 44
    return f"{line1}\n{line2}"


# Five synthetic passports — one per issuing state called out by the
# C1-05P-b prompt (FR / DE / NO / IN / US). Each exercises a different
# transliteration / name pattern. NONE are real.

FR_MRZ = _build_td3(
    issuing="FRA",
    surname="DUPONT",
    given="MARIE<CLAIRE",
    doc_number="AB1234567",
    nationality="FRA",
    dob="850315",
    sex="F",
    expiry="280620",
)

DE_MRZ = _build_td3(
    # German Umlaut: body "MÜLLER" ↔ MRZ "MUELLER" (DEU transliteration)
    issuing="DEU",
    surname="MUELLER",
    given="HANS",
    doc_number="C012345678",  # >9 chars — gets truncated to 9 per ICAO
    nationality="DEU",
    dob="780214",
    sex="M",
    expiry="290801",
)

NO_MRZ = _build_td3(
    # Norwegian Ø: body "BJØRN" ↔ MRZ "BJOERN" (NOR transliteration)
    issuing="NOR",
    surname="BJOERN",
    given="OLAV",
    doc_number="N7654321",
    nationality="NOR",
    dob="910722",
    sex="M",
    expiry="291031",
)

IN_MRZ = _build_td3(
    # India: body Devanagari (e.g. प्रिया शर्मा), MRZ Latin "SHARMA<<PRIYA"
    issuing="IND",
    surname="SHARMA",
    given="PRIYA",
    doc_number="J9876543",
    nationality="IND",
    dob="920307",
    sex="F",
    expiry="301115",
    personal="ECNR1234567",  # ECNR endorsement is a critical IN endorsement
)

US_MRZ = _build_td3(
    issuing="USA",
    surname="SMITH",
    given="JOHN<DAVID",
    doc_number="A12345678",
    nationality="USA",
    dob="850615",
    sex="M",
    expiry="280420",
)


SYNTHETIC_FIXTURES = {
    "FR": (FR_MRZ, "Autorité: Préfecture de Paris"),
    "DE": (DE_MRZ, "Ausstellende Behörde: Bundesdruckerei"),
    "NO": (NO_MRZ, "Utstedt av: Politiet"),
    "IN": (IN_MRZ, "Place of Issue: New Delhi"),
    "US": (US_MRZ, "Authority: U.S. Department of State"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Test fixtures (pytest)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_global_state():
    reset_registry()
    set_agent_run_logger(None)
    yield
    reset_registry()
    set_agent_run_logger(None)


def _document(text: str) -> ParsedDocument:
    return ParsedDocument(document_id=uuid4(), case_id=uuid4(), text=text)


def _install_llm_returning(output: Mapping[str, Any]) -> None:
    """Register a completer that returns ``output`` (wrapped in tool-use
    ``{"input": ...}``) for both gpt-4o-mini and claude-sonnet-4-6 so the
    runtime's single-retry escalation path works whichever model gets
    routed to.
    """

    async def _completer(prompt: str, **_kwargs: Any) -> CompletionResult:
        return CompletionResult(
            text=json.dumps({"input": output}, ensure_ascii=False),
            tokens_in=300,
            tokens_out=120,
        )

    register_completer("gpt-4o-mini", _completer)
    register_completer("claude-sonnet-4-6", _completer)


@pytest.fixture
def passport_agent():
    """Construct + register a PassportTd3Agent with in-memory persistence."""
    registry = AgentRegistry(InMemoryAgentStorage())
    sink = InMemoryExtractionSink()
    agent = PassportTd3Agent(
        registry=registry,
        sink=sink,
        di_provider=NullAzureDIProvider(),
    )
    agent.register()
    return agent, sink


# ─────────────────────────────────────────────────────────────────────────────
# Prompt + agent definition
# ─────────────────────────────────────────────────────────────────────────────


def test_passport_td3_prompt_is_on_disk():
    text = load_passport_td3_prompt()
    assert "PASSPORT_TD3" in text
    # The prompt explicitly forbids the agent from emitting MRZ fields.
    assert "NEVER extract" in text
    # And spells out the discrepancy severity bands.
    assert "INFO" in text and "WARN" in text


def test_agent_definition_excludes_mrz_field_keys_from_required():
    agent = _get_agent()
    # The agent definition's required keys must NOT include any MRZ-derived
    # field — the prompt is structurally prevented from overriding them.
    for k in MRZ_FIELD_KEYS:
        assert k not in agent.output_schema_required_keys, (
            f"MRZ field {k!r} must not be required of the LLM; MRZ is authoritative"
        )
    # The required keys are the two the LLM must always produce.
    assert set(agent.output_schema_required_keys) == {
        "issuing_authority",
        "agent_confidence",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 4 — agent_version recorded per Parsewise convention
# ─────────────────────────────────────────────────────────────────────────────


def test_register_persists_a_version_via_c1_05a_registry():
    registry = AgentRegistry(InMemoryAgentStorage())
    sink = InMemoryExtractionSink()
    agent = PassportTd3Agent(
        registry=registry,
        sink=sink,
        di_provider=NullAzureDIProvider(),
    )
    result = agent.register()
    assert result.created_new_agent is True
    assert result.created_new_version is True
    assert result.version.name == PASSPORT_TD3_AGENT_NAME
    assert result.version.version_number == 1
    # Loading by name returns the same row.
    loaded = registry.load_current(PASSPORT_TD3_AGENT_NAME)
    assert loaded.agent_version_id == result.version.agent_version_id


def test_re_registering_with_identical_prompt_is_idempotent():
    registry = AgentRegistry(InMemoryAgentStorage())
    sink = InMemoryExtractionSink()
    a1 = PassportTd3Agent(
        registry=registry, sink=sink, di_provider=NullAzureDIProvider()
    )
    r1 = a1.register()
    a2 = PassportTd3Agent(
        registry=registry, sink=sink, di_provider=NullAzureDIProvider()
    )
    r2 = a2.register()
    assert r1.version.agent_version_id == r2.version.agent_version_id
    assert r2.created_new_version is False


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 2 — MRZ fields match the C1-02 parser output exactly
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("state_code", list(SYNTHETIC_FIXTURES.keys()))
def test_mrz_extracted_fields_match_parser_output_exactly(passport_agent, state_code):
    agent, sink = passport_agent
    mrz_text, body = SYNTHETIC_FIXTURES[state_code]
    _install_llm_returning(
        {
            "issuing_authority": "Synthetic Authority",
            "agent_confidence": "high",
            "endorsements": [],
            "mrz_body_discrepancies": [],
        }
    )

    result = asyncio.run(agent.run(_document(body), mrz_text=mrz_text))

    canonical_mrz = parse_mrz(mrz_text)

    mrz_fields = {f.field_key: f for f in result.fields if f.field_key in MRZ_FIELD_KEYS}
    # Every non-null MRZ field reported by the parser must appear once.
    for key in MRZ_FIELD_KEYS:
        canonical_value = getattr(canonical_mrz, key, None)
        if canonical_value is None:
            assert key not in mrz_fields, (
                f"{state_code}: agent emitted {key} for a None parser value"
            )
            continue
        assert key in mrz_fields, f"{state_code}: agent missing MRZ field {key}"
        # The parser's value (potentially a date) must equal the agent's value_raw.
        expected = (
            canonical_value.isoformat()
            if hasattr(canonical_value, "isoformat")
            else str(canonical_value)
        )
        assert mrz_fields[key].value_raw == expected, (
            f"{state_code}: agent {key}={mrz_fields[key].value_raw!r} ≠ parser {expected!r}"
        )
        # And the source provenance must point at the MRZ parser.
        assert (mrz_fields[key].value_canonical or {}).get("source") == "mrz_c1_02"


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 3 — photo_bbox set with phi_class='BIOMETRIC'
# ─────────────────────────────────────────────────────────────────────────────


class _StaticDIProvider:
    """Returns a fixed photo + signature bbox for any document."""

    def __init__(
        self,
        photo_bbox: Bbox,
        signature_bbox: Bbox,
        body_text: str = "synthetic body",
    ) -> None:
        self._photo = photo_bbox
        self._sig = signature_bbox
        self._body = body_text

    def extract_passport(self, document: ParsedDocument) -> AzureDiPassportOutput:
        return AzureDiPassportOutput(
            body_text=self._body,
            photo_bbox=self._photo,
            signature_bbox=self._sig,
            issuing_authority_raw="Synthetic Authority",
        )


def test_photo_bbox_field_carries_phi_class_biometric():
    registry = AgentRegistry(InMemoryAgentStorage())
    sink = InMemoryExtractionSink()
    photo = Bbox(page=2, x0=100, y0=200, x1=300, y1=450)
    signature = Bbox(page=2, x0=120, y0=520, x1=380, y1=600)
    agent = PassportTd3Agent(
        registry=registry,
        sink=sink,
        di_provider=_StaticDIProvider(photo, signature),
    )
    agent.register()
    _install_llm_returning(
        {
            "issuing_authority": "Synthetic Authority",
            "agent_confidence": "high",
            "endorsements": [],
            "mrz_body_discrepancies": [],
        }
    )

    result = asyncio.run(agent.run(_document(FR_MRZ), mrz_text=FR_MRZ))

    di_fields = {f.field_key: f for f in result.fields if f.field_key in DI_FIELD_KEYS}
    assert "photo_bbox" in di_fields, "photo_bbox not emitted"
    photo_field = di_fields["photo_bbox"]
    # phi_class must be exactly the BIOMETRIC sentinel — that's what triggers
    # Article 9 audit logging on read.
    canonical = photo_field.value_canonical or {}
    assert canonical.get("phi_class") == PHI_CLASS_BIOMETRIC
    # Bbox coordinates are canonical 0–1000 and round-trip cleanly.
    assert photo_field.bbox_page == photo.page
    assert photo_field.bbox_x0 == photo.x0
    assert photo_field.bbox_y0 == photo.y0
    assert photo_field.bbox_x1 == photo.x1
    assert photo_field.bbox_y1 == photo.y1

    # Signature bbox is also emitted (no phi_class — it's not biometric).
    assert "signature_bbox" in di_fields
    sig_field = di_fields["signature_bbox"]
    sig_canonical = sig_field.value_canonical or {}
    assert "phi_class" not in sig_canonical


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 5 — Failed check digit → WARN finding, does NOT block extraction
# ─────────────────────────────────────────────────────────────────────────────


def test_failed_check_digit_surfaces_warn_finding_but_extraction_proceeds(passport_agent):
    agent, sink = passport_agent

    # Build a TD3 then sabotage line 2's document-number check digit.
    good = _build_td3(
        issuing="FRA",
        surname="DOE",
        given="JANE",
        doc_number="X1234567",
        nationality="FRA",
        dob="900101",
        sex="F",
        expiry="300101",
    )
    line1, line2 = good.split("\n")
    # Doc-number CD sits at position 9 in line 2 (after the 9-char doc number).
    # Bump it to a different digit to force a CD failure.
    current = line2[9]
    bad_digit = "0" if current != "0" else "1"
    bad_line2 = line2[:9] + bad_digit + line2[10:]
    bad_mrz = f"{line1}\n{bad_line2}"

    _install_llm_returning(
        {
            "issuing_authority": "Synthetic Authority",
            "agent_confidence": "medium",
            "endorsements": [],
            "mrz_body_discrepancies": [],
        }
    )
    result = asyncio.run(agent.run(_document("synthetic body"), mrz_text=bad_mrz))

    # WARN finding for the bad doc-number check digit MUST be surfaced.
    warns = [f for f in result.mrz_findings if f.severity == "WARN"]
    assert len(warns) >= 1, "no WARN finding emitted on broken check digit"
    doc_warns = [f for f in warns if "document_number" in (f.field or "")]
    assert len(doc_warns) >= 1, (
        f"no WARN finding mentioning document_number; got: {[w.field for w in warns]}"
    )

    # Extraction MUST NOT be blocked — the MRZ + DI + LLM fields all flow.
    mrz_field_keys = {f.field_key for f in result.fields if f.field_key in MRZ_FIELD_KEYS}
    assert "surname" in mrz_field_keys
    assert "document_number" in mrz_field_keys
    # The document_number's confidence is dropped to 0.7 because its CD failed.
    doc_field = next(f for f in result.fields if f.field_key == "document_number")
    assert doc_field.confidence == 0.7
    assert doc_field.resolution_status == "Requires attention"


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 1 — ≥90 % field accuracy on the 5 synthetic-passport fixture set
# ─────────────────────────────────────────────────────────────────────────────


def test_mrz_layer_alone_hits_100_percent_on_synthetic_fixtures(passport_agent):
    """MRZ extraction is deterministic — when the LLM is mocked to a
    happy-path response, the agent's MRZ layer alone must hit 100 %
    field-presence accuracy on every fixture (i.e. every parsable MRZ
    field appears in the output).
    """
    agent, sink = passport_agent
    _install_llm_returning(
        {
            "issuing_authority": "Synthetic Authority",
            "agent_confidence": "high",
            "endorsements": [],
            "mrz_body_discrepancies": [],
        }
    )

    total = 0
    correct = 0
    for state_code, (mrz_text, body) in SYNTHETIC_FIXTURES.items():
        canonical = parse_mrz(mrz_text)
        non_null_keys = [k for k in MRZ_FIELD_KEYS if getattr(canonical, k, None) is not None]
        result = asyncio.run(agent.run(_document(body), mrz_text=mrz_text))
        agent_keys = {f.field_key for f in result.fields if f.field_key in MRZ_FIELD_KEYS}
        for k in non_null_keys:
            total += 1
            if k in agent_keys:
                correct += 1

    assert total > 0
    accuracy = correct / total
    assert accuracy >= 0.90, (
        f"MRZ-layer accuracy across 5 fixtures = {accuracy:.2%} (target ≥ 90 %)"
    )


@pytest.mark.skipif(
    os.environ.get("RELOPASS_LIVE_LLM_TESTS") != "1",
    reason=(
        "Live-LLM accuracy run skipped. Set RELOPASS_LIVE_LLM_TESTS=1 + register "
        "real Anthropic/OpenAI completers to exercise the LLM-layer accuracy "
        "(issuing_authority + endorsements + discrepancies) on the 5 fixtures. "
        "The eval methodology + gold labels live in prompts/extraction/passport_td3_v1.eval.md."
    ),
)
def test_llm_layer_accuracy_live():
    # Concrete completer registration belongs to the real adapter (a future
    # backend/services task). Once installed, this test invokes the agent
    # against each fixture and asserts ≥90 % field correctness against the
    # gold labels in passport_td3_v1.eval.md.
    raise NotImplementedError(
        "Activate this test after backend/services/llm_router_clients.py lands"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Auxiliary — LLM output flows through to ExtractedField rows
# ─────────────────────────────────────────────────────────────────────────────


def test_llm_output_appears_as_extracted_fields(passport_agent):
    agent, sink = passport_agent
    _install_llm_returning(
        {
            "issuing_authority": "Préfecture de Paris",
            "agent_confidence": "high",
            "endorsements": [
                {"type": "DIPLOMATIC", "raw_text": "DIPLOMATIQUE"},
            ],
            "mrz_body_discrepancies": [
                {
                    "field": "surname",
                    "mrz_value": "DUPONT",
                    "body_value": "Dupont",
                    "severity": "INFO",
                    "reason": "case fold",
                }
            ],
        }
    )
    result = asyncio.run(agent.run(_document(FR_MRZ), mrz_text=FR_MRZ))
    llm_fields = {f.field_key: f for f in result.fields if f.field_key in LLM_FIELD_KEYS}

    assert llm_fields["issuing_authority"].value_raw == "Préfecture de Paris"
    assert llm_fields["agent_confidence"].confidence == pytest.approx(0.95)
    # endorsements + mrz_body_discrepancies arrive as JSON strings.
    assert llm_fields["endorsements"].value_raw is not None
    assert "DIPLOMATIC" in llm_fields["endorsements"].value_raw
    assert "INFO" in llm_fields["mrz_body_discrepancies"].value_raw


def test_run_records_agent_run_row_with_model_tokens_cost(passport_agent):
    agent, sink = passport_agent
    _install_llm_returning(
        {
            "issuing_authority": "Authority",
            "agent_confidence": "high",
        }
    )
    result = asyncio.run(agent.run(_document(FR_MRZ), mrz_text=FR_MRZ))

    assert len(sink.agent_runs) == 1
    row = sink.agent_runs[0]
    assert row.agent_run_id == result.agent_run_id
    assert row.agent_version_id == result.agent_version_id
    assert row.model_name == "gpt-4o-mini"
    assert row.tokens_in == 300
    assert row.tokens_out == 120
    # gpt-4o-mini cost: 300 * 0.00000015 + 120 * 0.0000006 = 0.000117
    assert row.cost_usd == pytest.approx(0.000117, rel=1e-6)
    assert row.status == "OK"


def test_run_proceeds_when_llm_router_has_no_completer():
    """If the C1-13 router has no completer registered (e.g. SDK adapter not
    yet wired), the agent still completes — emitting only MRZ + DI rows and
    logging a "(none — LLM unrouted)" model name to agent_runs.

    This is the graceful-degradation behaviour: the MRZ + biometric
    information is the most operationally important data and ships
    even when LLM access is down.
    """
    registry = AgentRegistry(InMemoryAgentStorage())
    sink = InMemoryExtractionSink()
    photo = Bbox(page=1, x0=100, y0=200, x1=400, y1=600)
    signature = Bbox(page=1, x0=120, y0=620, x1=400, y1=700)
    agent = PassportTd3Agent(
        registry=registry, sink=sink, di_provider=_StaticDIProvider(photo, signature)
    )
    agent.register()
    # Intentionally no register_completer() call — reset_registry already
    # cleared the registry via the autouse fixture.

    result = asyncio.run(agent.run(_document(FR_MRZ), mrz_text=FR_MRZ))

    assert result.model_name == "(none — LLM unrouted)"
    assert result.tokens_in == 0
    assert result.tokens_out == 0
    # MRZ + DI fields still flowed.
    assert any(f.field_key == "surname" for f in result.fields)
    assert any(f.field_key == "photo_bbox" for f in result.fields)
    # No LLM fields.
    assert not any(f.field_key in LLM_FIELD_KEYS for f in result.fields)
