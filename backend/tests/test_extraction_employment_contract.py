"""AIQ-1766 · Tests for the EMPLOYMENT_CONTRACT extraction agent.

Mirrors the visa-permit test pattern (in-memory registry + sink, a mock LLM
completer, assertions on the emitted ExtractedField tuple). Covers:

1. All three locale prompts load from disk; no new prompt is authored.
2. Jurisdiction is read from the document text, and an undetectable locale
   returns None rather than guessing — with the LLM never called.
3. The agent is wired into EXTRACTION_AGENT_REGISTRY under EMPLOYMENT_CONTRACT.
4. FR/DE/NO happy paths emit the prompt's field keys with per-field confidence.
5. mask_pii() is applied to the document text BEFORE the LLM call.
6. Registry IDs survive masking via on-platform recovery from raw text.
7. Fail-soft: unparseable salary, non-contract payload, and undetectable locale
   all return a result and never raise.
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from typing import Any, Dict, List, Mapping
from uuid import uuid4

import pytest

from backend.app.services.rce_document_ingest import classify_rce_document_type
from backend.relopass.agents import (
    AgentRegistry,
    InMemoryAgentStorage,
    ParsedDocument,
)
from backend.relopass.agents.extraction import (
    EMPLOYMENT_CONTRACT_DOCUMENT_TYPE,
    EXTRACTION_AGENT_REGISTRY,
    EmploymentContractAgent,
    detect_jurisdiction,
    get_extraction_agent_class,
    is_guaranteed_fixed_only,
    load_employment_contract_prompt,
    recover_registry_id,
)
from backend.relopass.agents.runtime import InMemoryExtractionSink
from backend.relopass.llm import register_completer, reset_registry
from backend.relopass.llm.router import CompletionResult, set_agent_run_logger

# ─────────────────────────────────────────────────────────────────────────────
# Document fixtures — real contract prose, because the agent reads the raw text
# for jurisdiction detection, registry-ID recovery and the variable-pay check.
# Each carries a person name and a registry ID so the masking assertions bite.
# ─────────────────────────────────────────────────────────────────────────────

FR_CDI_TEXT = """CONTRAT DE TRAVAIL À DURÉE INDÉTERMINÉE

Entre Acme France SAS, dont le siège est sis à Paris, SIREN 552 120 222,
et Madame Marie Dupont, ci-après "le Salarié".

Article 3 - Rémunération
La rémunération brute mensuelle est fixée à 4 200,00 €.

Article 4 - Date d'effet
Le présent contrat prend effet le 1er septembre 2026.

Article 5 - Durée du travail
Temps plein, 35 heures hebdomadaires (100 %). Période d'essai de trois mois.
"""

DE_AV_TEXT = """ARBEITSVERTRAG

zwischen der Beispiel GmbH, eingetragen im Handelsregister HRB 12345 beim
Amtsgericht München, und Frau Anna Müller ("Arbeitnehmerin").

§ 3 Vergütung
Das monatliche Bruttogehalt beträgt 5.800,00 €.

§ 5 Beginn
Das Arbeitsverhältnis beginnt am 01.10.2026.

§ 6 Arbeitszeit
Vollzeit, 40 Stunden pro Woche. Probezeit: sechs Monate. Kündigungsfrist: drei Monate.
"""

NO_AK_TEXT = """ARBEIDSAVTALE

mellom Eksempel AS, organisasjonsnummer 998 877 665, og Olav Hansen
("Arbeidstaker"). Avtalen følger arbeidsmiljøloven.

§ 4 Lønn
Brutto månedslønn: 65 000 NOK.

§ 5 Tiltredelse
Arbeidsforholdet starter 01.11.2026.

§ 6 Arbeidstid
Stillingsprosent: 100. Prøvetid: seks måneder.
"""

# ─────────────────────────────────────────────────────────────────────────────
# LLM payloads — the MERGED prompt schema (gross_salary_annual as a 2-dp string
# already annualised by the prompt, currency_iso3, per-field confidence bands).
# ─────────────────────────────────────────────────────────────────────────────

FR_PAYLOAD: Dict[str, Any] = {
    "is_employment_contract": True,
    "contract_type": "CDI",
    "employer_legal_name": "Acme France SAS",
    # Masked out of the prompt for FR — the agent recovers it from raw text.
    "employer_registry_id": None,
    "employer_registry_id_kind": None,
    "position_title": "Analyste de données senior",
    "position_isco_2008": "2511",
    "gross_salary_annual": "50400.00",
    "currency_iso3": "EUR",
    "gross_salary_guaranteed_fixed_only_bool": True,
    "contract_start_date": "2026-09-01",
    "contract_duration_months": None,
    "working_time_percent": 100,
    "employer_legal_name_confidence": "high",
    "position_title_confidence": "high",
    "gross_salary_annual_confidence": "medium",
    "contract_start_date_confidence": "high",
    "working_time_percent_confidence": "low",
}

DE_PAYLOAD: Dict[str, Any] = {
    "is_employment_contract": True,
    "contract_type": "UNBEFRISTET",
    "employer_legal_name": "Beispiel GmbH",
    # DE "HRB 12345" survives masking, so the LLM does return it.
    "employer_registry_id": "HRB 12345",
    "employer_registry_id_kind": "HRB",
    "position_title": "Senior Datenanalystin",
    "position_isco_2008": "2511",
    "gross_salary_annual": "75400.00",
    "currency_iso3": "EUR",
    "gross_salary_guaranteed_fixed_only_bool": True,
    "contract_start_date": "2026-10-01",
    "contract_duration_months": None,
    "working_time_percent": 100,
    "employer_legal_name_confidence": "high",
    "gross_salary_annual_confidence": "high",
    "contract_start_date_confidence": "high",
}

NO_PAYLOAD: Dict[str, Any] = {
    "is_employment_contract": True,
    "contract_type": "FAST",
    "employer_legal_name": "Eksempel AS",
    "employer_registry_id": None,
    "employer_registry_id_kind": None,
    "position_title": "Seniorrådgiver fornybar energi",
    "position_isco_2008": "2149",
    "gross_salary_annual": "839800.00",
    "currency_iso3": "NOK",
    "gross_salary_guaranteed_fixed_only_bool": True,
    "contract_start_date": "2026-11-01",
    "contract_duration_months": None,
    "working_time_percent": 100,
    "employer_legal_name_confidence": "high",
    "gross_salary_annual_confidence": "medium",
}

NOT_A_CONTRACT: Dict[str, Any] = {
    "is_employment_contract": False,
    "employer_legal_name": None,
    "gross_salary_annual": None,
    "currency_iso3": None,
}

CASES = {
    "FR": (FR_CDI_TEXT, FR_PAYLOAD, "552120222", "SIREN"),
    "DE": (DE_AV_TEXT, DE_PAYLOAD, "HRB 12345", "HRB"),
    "NO": (NO_AK_TEXT, NO_PAYLOAD, "998877665", "ORGNR"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Harness
# ─────────────────────────────────────────────────────────────────────────────


def _document(text: str) -> ParsedDocument:
    return ParsedDocument(document_id=uuid4(), case_id=uuid4(), text=text)


def _install_completer(payload: Mapping[str, Any]) -> List[str]:
    """Register the stub on both the default model and the escalation target.
    Returns the list the captured prompts land in, so tests can assert on what
    would actually have been sent to the vendor."""
    seen: List[str] = []

    async def _completer(prompt: str, **_kwargs: Any) -> CompletionResult:
        seen.append(prompt)
        return CompletionResult(
            text=json.dumps({"input": payload}, ensure_ascii=False),
            tokens_in=900,
            tokens_out=220,
        )

    register_completer("gpt-4o-mini", _completer)
    register_completer("claude-sonnet-4-6", _completer)
    return seen


@pytest.fixture(autouse=True)
def _reset_state():
    reset_registry()
    set_agent_run_logger(None)
    yield
    reset_registry()
    set_agent_run_logger(None)


def _agent() -> EmploymentContractAgent:
    agent = EmploymentContractAgent(
        registry=AgentRegistry(InMemoryAgentStorage()),
        sink=InMemoryExtractionSink(),
    )
    agent.register()
    return agent


def _by_key(result) -> Dict[str, Any]:
    return {f.field_key: f for f in result.fields}


# ─────────────────────────────────────────────────────────────────────────────
# Prompts + wiring
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("jurisdiction", ["FR", "DE", "NO"])
def test_prompt_loads_from_disk(jurisdiction):
    """Criterion 4 — the three merged prompts are reused, none is authored."""
    prompt = load_employment_contract_prompt(jurisdiction)
    assert "extract_employment_contract" in prompt
    assert "gross_salary_annual" in prompt


def test_registry_wires_employment_contract():
    """Criterion 3 — reachable, not merely defined."""
    assert get_extraction_agent_class(EMPLOYMENT_CONTRACT_DOCUMENT_TYPE) is (
        EmploymentContractAgent
    )
    assert EMPLOYMENT_CONTRACT_DOCUMENT_TYPE in EXTRACTION_AGENT_REGISTRY


def test_orchestrator_resolves_the_agent():
    from backend.app.services.rce_extraction_orchestrator import _agent_class

    assert _agent_class("EMPLOYMENT_CONTRACT") is EmploymentContractAgent
    # The bare "CONTRACT" code has no agent and must stay unrouted.
    assert _agent_class("CONTRACT") is None


@pytest.mark.parametrize(
    "file_name",
    [
        "employment_contract.pdf",
        "contrat_de_travail_signe.pdf",
        "Arbeitsvertrag_2026.pdf",
        "arbeidsavtale.pdf",
        "cdi_signed.pdf",
    ],
)
def test_classifier_routes_employment_contract(file_name):
    assert classify_rce_document_type(file_name) == "EMPLOYMENT_CONTRACT"


def test_contract_branch_does_not_shadow_more_specific_types():
    """The contract token is broad, so it must lose to a locale tax token."""
    assert classify_rce_document_type("lohnsteuer_contract_2025.pdf") == "TAX_CERT_DE"
    assert classify_rce_document_type("passport_contract.pdf") == "PASSPORT_TD3"


# ─────────────────────────────────────────────────────────────────────────────
# Jurisdiction detection
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("expected", ["FR", "DE", "NO"])
def test_detect_jurisdiction_from_document_text(expected):
    text, _, _, _ = CASES[expected]
    assert detect_jurisdiction(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Invoice #4471 for catering services rendered on 3 June.",
        "This document has no contractual vocabulary whatsoever.",
    ],
)
def test_detect_jurisdiction_returns_none_rather_than_guessing(text):
    assert detect_jurisdiction(text) is None


def test_undetectable_locale_skips_the_llm_entirely():
    """Criterion 5 — fail-soft, and it must not burn a paid call to do it."""
    seen = _install_completer(FR_PAYLOAD)
    result = asyncio.run(_agent().run(_document("Nothing contractual here at all.")))

    assert result.fields == ()
    assert result.skipped_reason == "jurisdiction_undetected"
    assert result.jurisdiction is None
    assert seen == [], "the LLM must not be called when no locale can be read"


# ─────────────────────────────────────────────────────────────────────────────
# Happy paths
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("jurisdiction", ["FR", "DE", "NO"])
def test_emits_the_prompt_field_keys_with_confidence(jurisdiction):
    """Criterion 1 — the five load-bearing values, each with per-field confidence.

    Names are the PROMPT's (employer_legal_name / position_title /
    gross_salary_annual / currency_iso3 / contract_start_date), not the Notion
    task's, because contradiction.py's COHORT_1_FIELD_KEYS is keyed on these.
    """
    text, payload, _, _ = CASES[jurisdiction]
    _install_completer(payload)
    result = asyncio.run(_agent().run(_document(text)))

    fields = _by_key(result)
    for key in (
        "employer_legal_name",
        "position_title",
        "gross_salary_annual",
        "currency_iso3",
        "contract_start_date",
    ):
        assert key in fields, f"{key} missing for {jurisdiction}"
        assert fields[key].value_raw

    assert result.jurisdiction == jurisdiction
    assert result.skipped_reason is None
    assert fields["currency_iso3"].value_raw == payload["currency_iso3"]
    assert fields["contract_start_date"].value_raw == payload["contract_start_date"]


def test_confidence_bands_map_to_distinct_floats():
    """high/medium/low must not collapse to one number."""
    _install_completer(FR_PAYLOAD)
    fields = _by_key(asyncio.run(_agent().run(_document(FR_CDI_TEXT))))

    assert fields["employer_legal_name"].confidence == 0.95  # high
    assert fields["gross_salary_annual"].confidence == 0.75  # medium
    assert fields["working_time_percent"].confidence == 0.50  # low
    # No band emitted for contract_type → make_field's default.
    assert fields["contract_type"].confidence == 0.9


def test_salary_is_parsed_not_recomputed():
    """The prompt annualises; the agent must carry that number through intact."""
    _install_completer(NO_PAYLOAD)
    result = asyncio.run(_agent().run(_document(NO_AK_TEXT)))

    assert result.gross_salary_annual == Decimal("839800.00")
    assert _by_key(result)["gross_salary_annual"].value_raw == "839800.00"
    assert result.currency_iso3 == "NOK"


# ─────────────────────────────────────────────────────────────────────────────
# PII masking (criterion 2) + registry-ID recovery
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("jurisdiction", ["FR", "DE", "NO"])
def test_mask_pii_is_applied_before_the_llm_call(jurisdiction):
    """Criterion 2 — the document text reaching the sub-processor is masked."""
    text, payload, _, _ = CASES[jurisdiction]
    seen = _install_completer(payload)
    asyncio.run(_agent().run(_document(text)))

    assert len(seen) == 1
    document_part = seen[0].split("=== DOCUMENT TEXT ===", 1)[1]
    assert "[REDACTED_" in document_part, "masking did not run"
    assert document_part != text, "unmasked document text reached the LLM"


@pytest.mark.parametrize(
    "jurisdiction,person_name",
    [("FR", "Marie Dupont"), ("DE", "Anna Müller")],
)
def test_cued_person_names_are_redacted(jurisdiction, person_name):
    """Names carrying an honorific ("Madame", "Frau") are removed."""
    text, payload, _, _ = CASES[jurisdiction]
    seen = _install_completer(payload)
    asyncio.run(_agent().run(_document(text)))

    document_part = seen[0].split("=== DOCUMENT TEXT ===", 1)[1]
    assert person_name not in document_part
    assert "[REDACTED_PERSON]" in document_part


def test_uncued_person_name_is_a_known_masker_gap():
    """DOCUMENTS A RESIDUAL EXPOSURE, it does not endorse it.

    `mask_pii`'s name detector is context-boosted: it fires on an honorific
    (Madame / Frau / herr / fru) or a name cue (født, geboren, né). The NO
    fixture writes "og Olav Hansen" with neither, so the name survives masking
    and reaches the LLM. That is a limitation of the shared masker — its own
    docstring defers bare un-cued names to a presidio+spaCy NER pass — and it
    affects every LLM path, not just this agent, so it is deliberately NOT
    patched here. Tracked as a follow-up.

    This test pins the CURRENT behaviour so the gap is visible in CI. When the
    NER pass lands it will fail loudly, which is the point: that is the signal
    to delete it, not to widen the exemption.
    """
    seen = _install_completer(NO_PAYLOAD)
    asyncio.run(_agent().run(_document(NO_AK_TEXT)))
    document_part = seen[0].split("=== DOCUMENT TEXT ===", 1)[1]

    assert "Olav Hansen" in document_part  # ← the gap
    # The same name IS redacted once a cue is present, proving the mechanism.
    from backend.app.services.pii_masker import mask_pii

    assert "Olav Hansen" not in mask_pii("og herr Olav Hansen")


def test_masking_redacts_the_fr_siren_from_the_prompt():
    """The precise collision this design works around: a 9-digit space-grouped
    SIREN is indistinguishable from a phone number, so masking eats it."""
    seen = _install_completer(FR_PAYLOAD)
    asyncio.run(_agent().run(_document(FR_CDI_TEXT)))

    document_part = seen[0].split("=== DOCUMENT TEXT ===", 1)[1]
    assert "552 120 222" not in document_part


@pytest.mark.parametrize("jurisdiction", ["FR", "DE", "NO"])
def test_registry_id_survives_masking(jurisdiction):
    """...and is still extracted, recovered on-platform from the raw text."""
    text, payload, expected_id, expected_kind = CASES[jurisdiction]
    _install_completer(payload)
    fields = _by_key(asyncio.run(_agent().run(_document(text))))

    assert "employer_registry_id" in fields
    assert fields["employer_registry_id"].value_raw == expected_id
    assert fields["employer_registry_id"].value_canonical["kind"] == expected_kind


def test_registry_id_records_whether_it_was_recovered():
    """FR/NO come from raw-text recovery; DE comes back from the LLM."""
    _install_completer(FR_PAYLOAD)
    fr = _by_key(asyncio.run(_agent().run(_document(FR_CDI_TEXT))))
    assert fr["employer_registry_id"].value_canonical["recovered_from_raw_text"] is True

    reset_registry()
    _install_completer(DE_PAYLOAD)
    de = _by_key(asyncio.run(_agent().run(_document(DE_AV_TEXT))))
    assert de["employer_registry_id"].value_canonical["recovered_from_raw_text"] is False


@pytest.mark.parametrize("jurisdiction", ["FR", "DE", "NO"])
def test_recover_registry_id_needs_a_cue_word(jurisdiction):
    text, _, expected_id, _ = CASES[jurisdiction]
    assert recover_registry_id(text, jurisdiction) == expected_id
    # A bare number with no cue must not be mistaken for a company ID.
    assert recover_registry_id("Reference 552 120 222 on page 4.", jurisdiction) is None


# ─────────────────────────────────────────────────────────────────────────────
# Variable-pay cross-check
# ─────────────────────────────────────────────────────────────────────────────


def test_variable_pay_in_text_overrides_the_llm_fixed_only_claim():
    """This binary gates the IN→DE Blue Card threshold check, so a text mention
    of variable pay must win over a model that claimed 'fixed only'."""
    text = FR_CDI_TEXT + "\nArticle 8 — Prime variable jusqu'à 15 % des objectifs."
    _install_completer(FR_PAYLOAD)  # claims gross_salary_guaranteed_fixed_only = True
    result = asyncio.run(_agent().run(_document(text)))

    assert result.guaranteed_fixed_only is False
    field = _by_key(result)["gross_salary_guaranteed_fixed_only_bool"]
    assert field.value_raw == "false"
    assert field.value_canonical["llm_value"] is True
    assert field.value_canonical["text_heuristic_value"] is False


def test_is_guaranteed_fixed_only_detects_common_variable_pay_terms():
    assert is_guaranteed_fixed_only(FR_CDI_TEXT) is True
    for phrase in ("bonus", "commission", "stock option", "provisjon", "Erfolgsbeteiligung"):
        assert is_guaranteed_fixed_only(f"{FR_CDI_TEXT}\n{phrase} applies.") is False


# ─────────────────────────────────────────────────────────────────────────────
# Fail-soft (criterion 5)
# ─────────────────────────────────────────────────────────────────────────────


def test_non_contract_payload_yields_no_fields():
    _install_completer(NOT_A_CONTRACT)
    result = asyncio.run(_agent().run(_document(FR_CDI_TEXT)))

    assert result.fields == ()
    assert result.skipped_reason == "not_an_employment_contract"


@pytest.mark.parametrize("bad_salary", ["not-a-number", "", None, "-4000.00", "1.2.3"])
def test_unparseable_salary_drops_the_field_without_raising(bad_salary):
    payload = dict(FR_PAYLOAD, gross_salary_annual=bad_salary)
    _install_completer(payload)
    result = asyncio.run(_agent().run(_document(FR_CDI_TEXT)))

    assert result.gross_salary_annual is None
    assert "gross_salary_annual" not in _by_key(result)
    # The rest of the extraction still lands.
    assert "employer_legal_name" in _by_key(result)


def test_run_before_register_raises_a_clear_error():
    agent = EmploymentContractAgent(
        registry=AgentRegistry(InMemoryAgentStorage()),
        sink=InMemoryExtractionSink(),
    )
    with pytest.raises(RuntimeError, match="before register"):
        asyncio.run(agent.run(_document(FR_CDI_TEXT)))
